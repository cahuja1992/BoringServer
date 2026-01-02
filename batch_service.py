"""Batch inference service for processing webdataset.

Supports img2dataset format with parquet metadata from both S3 and local filesystem.
"""

import argparse
import io
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional
from urllib.parse import urlparse

import boto3
import pandas as pd
import ray
import torch
from botocore.exceptions import ClientError
from PIL import Image
from tqdm import tqdm

from engine.config import load_config
from engine.loader import load_model, validate_model_interface
from engine.logging import get_logger, setup_logging
from engine.metrics import MetricsCollector
from engine.utils import decode_image


logger = get_logger(__name__)


class UnifiedDataLoader:
    """Unified data loader supporting both S3 and local filesystem."""

    def __init__(
        self,
        input_dir: str,
        aws_access_key: Optional[str] = None,
        aws_secret_key: Optional[str] = None,
        aws_region: Optional[str] = None,
    ):
        """Initialize unified data loader.

        Args:
            input_dir: Input directory (s3://bucket/prefix or local path)
            aws_access_key: AWS access key (or from env)
            aws_secret_key: AWS secret key (or from env)
            aws_region: AWS region (default: us-east-1)
        """
        self.input_dir = input_dir
        self.is_s3 = input_dir.startswith("s3://")

        if self.is_s3:
            # Parse S3 URL
            parsed = urlparse(input_dir)
            self.s3_bucket = parsed.netloc
            self.s3_prefix = parsed.path.lstrip("/")

            # Initialize S3 client
            session_kwargs = {}
            if aws_access_key and aws_secret_key:
                session_kwargs = {
                    "aws_access_key_id": aws_access_key,
                    "aws_secret_access_key": aws_secret_key,
                }

            self.s3_client = boto3.client(
                "s3", region_name=aws_region or "us-east-1", **session_kwargs
            )

            logger.info(f"S3 mode: s3://{self.s3_bucket}/{self.s3_prefix}")
        else:
            # Local filesystem
            self.local_path = Path(input_dir)
            if not self.local_path.exists():
                raise ValueError(f"Input directory does not exist: {input_dir}")

            logger.info(f"Local mode: {self.local_path}")

    def list_shards(self) -> List[str]:
        """List all parquet shards.

        Returns:
            List of shard paths (S3 keys or local paths)
        """
        shards = []

        if self.is_s3:
            # S3 mode
            paginator = self.s3_client.get_paginator("list_objects_v2")

            try:
                for page in paginator.paginate(
                    Bucket=self.s3_bucket, Prefix=self.s3_prefix
                ):
                    if "Contents" not in page:
                        continue

                    for obj in page["Contents"]:
                        key = obj["Key"]
                        if key.endswith(".parquet"):
                            shards.append(key)

                logger.info(f"Found {len(shards)} parquet shards in S3")
                return sorted(shards)

            except ClientError as e:
                logger.error(f"Failed to list S3 objects: {e}")
                raise
        else:
            # Local filesystem mode
            for parquet_file in self.local_path.glob("**/*.parquet"):
                shards.append(str(parquet_file))

            logger.info(f"Found {len(shards)} parquet shards locally")
            return sorted(shards)

    def load_shard(self, shard_path: str) -> pd.DataFrame:
        """Load a parquet shard.

        Args:
            shard_path: S3 key or local path to parquet file

        Returns:
            DataFrame with shard data
        """
        try:
            if self.is_s3:
                # Load from S3
                obj = self.s3_client.get_object(
                    Bucket=self.s3_bucket, Key=shard_path
                )
                parquet_buffer = io.BytesIO(obj["Body"].read())
                df = pd.read_parquet(parquet_buffer)
                logger.debug(f"Loaded S3 shard {shard_path}: {len(df)} rows")
            else:
                # Load from local filesystem
                df = pd.read_parquet(shard_path)
                logger.debug(f"Loaded local shard {shard_path}: {len(df)} rows")

            return df

        except Exception as e:
            logger.error(f"Failed to load shard {shard_path}: {e}")
            raise

    def load_image_from_url(self, image_url: str) -> Image.Image:
        """Load image from URL (S3 or local path).

        Args:
            image_url: Image URL (s3://bucket/key or local path)

        Returns:
            PIL Image
        """
        if image_url.startswith("s3://"):
            # Parse S3 URL
            parsed = urlparse(image_url)
            bucket = parsed.netloc
            key = parsed.path.lstrip("/")

            try:
                obj = self.s3_client.get_object(Bucket=bucket, Key=key)
                image_bytes = obj["Body"].read()
                return decode_image(image_bytes)
            except ClientError as e:
                logger.error(f"Failed to load image from S3: {image_url}, {e}")
                raise
        else:
            # Local filesystem
            try:
                with open(image_url, "rb") as f:
                    image_bytes = f.read()
                return decode_image(image_bytes)
            except Exception as e:
                logger.error(f"Failed to load local image: {image_url}, {e}")
                raise

    def iterate_samples(
        self, shard_paths: Optional[List[str]] = None
    ) -> Iterator[Dict[str, Any]]:
        """Iterate over all samples in shards.

        Args:
            shard_paths: Specific shards to process (None = all)

        Yields:
            Sample dict with: url, image (optional), caption, metadata
        """
        if shard_paths is None:
            shard_paths = self.list_shards()

        for shard_path in shard_paths:
            df = self.load_shard(shard_path)

            for idx, row in df.iterrows():
                sample = {
                    "url": row.get("url", ""),
                    "caption": row.get("caption", ""),
                    "key": row.get("key", ""),
                    "metadata": {},
                }

                # Add any additional columns as metadata
                for col in df.columns:
                    if col not in ["url", "caption", "key"]:
                        sample["metadata"][col] = row[col]

                yield sample


class UnifiedOutputWriter:
    """Unified output writer supporting both S3 and local filesystem."""

    def __init__(
        self,
        output_dir: str,
        aws_access_key: Optional[str] = None,
        aws_secret_key: Optional[str] = None,
        aws_region: Optional[str] = None,
    ):
        """Initialize unified output writer.

        Args:
            output_dir: Output directory (s3://bucket/prefix or local path)
            aws_access_key: AWS access key (or from env)
            aws_secret_key: AWS secret key (or from env)
            aws_region: AWS region (default: us-east-1)
        """
        self.output_dir = output_dir
        self.is_s3 = output_dir.startswith("s3://")

        if self.is_s3:
            # Parse S3 URL
            parsed = urlparse(output_dir)
            self.s3_bucket = parsed.netloc
            self.s3_prefix = parsed.path.lstrip("/")

            # Initialize S3 client
            session_kwargs = {}
            if aws_access_key and aws_secret_key:
                session_kwargs = {
                    "aws_access_key_id": aws_access_key,
                    "aws_secret_access_key": aws_secret_key,
                }

            self.s3_client = boto3.client(
                "s3", region_name=aws_region or "us-east-1", **session_kwargs
            )

            logger.info(f"Output to S3: s3://{self.s3_bucket}/{self.s3_prefix}")
        else:
            # Local filesystem
            self.local_path = Path(output_dir)
            self.local_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Output to local: {self.local_path}")

    def write_parquet(self, df: pd.DataFrame, filename: str) -> None:
        """Write DataFrame to parquet.

        Args:
            df: DataFrame to write
            filename: Output filename (e.g., 'embeddings.parquet')
        """
        if self.is_s3:
            # Write to S3
            buffer = io.BytesIO()
            df.to_parquet(buffer, index=False)
            buffer.seek(0)

            s3_key = f"{self.s3_prefix}/{filename}".lstrip("/")
            self.s3_client.put_object(
                Bucket=self.s3_bucket, Key=s3_key, Body=buffer.getvalue()
            )
            logger.info(f"Wrote parquet to s3://{self.s3_bucket}/{s3_key}")
        else:
            # Write to local filesystem
            output_file = self.local_path / filename
            df.to_parquet(output_file, index=False)
            logger.info(f"Wrote parquet to {output_file}")

    def write_json(self, data: dict, filename: str) -> None:
        """Write dict to JSON.

        Args:
            data: Dictionary to write
            filename: Output filename (e.g., 'metadata.json')
        """
        json_str = json.dumps(data, indent=2)

        if self.is_s3:
            # Write to S3
            s3_key = f"{self.s3_prefix}/{filename}".lstrip("/")
            self.s3_client.put_object(
                Bucket=self.s3_bucket, Key=s3_key, Body=json_str.encode()
            )
            logger.info(f"Wrote JSON to s3://{self.s3_bucket}/{s3_key}")
        else:
            # Write to local filesystem
            output_file = self.local_path / filename
            with open(output_file, "w") as f:
                f.write(json_str)
            logger.info(f"Wrote JSON to {output_file}")


@ray.remote(num_gpus=1 if torch.cuda.is_available() else 0)
class BatchInferenceWorker:
    """Ray actor for batch inference."""

    def __init__(self, model_directory: str, config):
        """Initialize worker.

        Args:
            model_directory: Path to model directory
            config: Service configuration
        """
        self.config = config
        self.model_directory = model_directory

        logger.info(f"Initializing BatchInferenceWorker for {model_directory}")

        # Load model
        start_time = time.time()
        self.model_info, self.model = load_model(model_directory)
        load_duration = time.time() - start_time

        # Validate interface
        validate_model_interface(self.model)

        # Initialize metrics
        self.metrics = MetricsCollector(self.model_info.name)
        self.metrics.record_model_load(load_duration)

        logger.info(f"Model loaded: {self.model_info.name} in {load_duration:.2f}s")

        # Load model weights
        self.model.load()
        logger.info("Model weights loaded")

        # Warmup
        if config.models.warmup_enabled:
            start_time = time.time()
            self.model.warmup()
            warmup_duration = time.time() - start_time
            self.metrics.record_model_warmup(warmup_duration)
            logger.info(f"Model warmed up in {warmup_duration:.2f}s")

        # Get batch configuration
        self.batch_size = self.model.batch_size()
        logger.info(f"Worker ready: batch_size={self.batch_size}")

    def process_batch(self, batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process a batch of samples.

        Args:
            batch: List of samples with images

        Returns:
            List of results with embeddings
        """
        start_time = time.time()

        try:
            # Prepare batch
            payloads = [
                {"image": sample["image"], "text": sample.get("caption")}
                for sample in batch
            ]

            # Run inference
            embeddings = self.model.encode(payloads)

            # Prepare results
            results = []
            for sample, embedding in zip(batch, embeddings):
                result = {
                    "url": sample["url"],
                    "key": sample.get("key", ""),
                    "caption": sample.get("caption", ""),
                    "embedding": embedding,
                    "metadata": sample.get("metadata", {}),
                }
                results.append(result)

            duration = time.time() - start_time
            self.metrics.record_batch(len(batch), duration)

            logger.debug(
                f"Processed batch: size={len(batch)}, duration={duration*1000:.2f}ms"
            )

            return results

        except Exception as e:
            logger.error(f"Batch processing failed: {e}", exc_info=True)
            self.metrics.record_error("processing_error")
            raise


class BatchInferenceOrchestrator:
    """Orchestrate batch inference across multiple workers."""

    def __init__(
        self,
        model_directory: str,
        config,
        num_workers: int = 4,
        batch_size: Optional[int] = None,
    ):
        """Initialize orchestrator.

        Args:
            model_directory: Path to model directory
            config: Service configuration
            num_workers: Number of Ray workers
            batch_size: Batch size per worker (None = use model default)
        """
        self.model_directory = model_directory
        self.config = config
        self.num_workers = num_workers
        self.batch_size = batch_size

        logger.info(f"Initializing orchestrator with {num_workers} workers")

        # Create workers
        self.workers = [
            BatchInferenceWorker.remote(model_directory, config)
            for _ in range(num_workers)
        ]

        logger.info("All workers initialized")

    def process_dataset(
        self,
        data_loader: UnifiedDataLoader,
        output_writer: UnifiedOutputWriter,
        load_images: bool = True,
        max_samples: Optional[int] = None,
    ) -> None:
        """Process entire dataset.

        Args:
            data_loader: Data loader
            output_writer: Output writer
            load_images: Whether to load images (False = use pre-loaded paths)
            max_samples: Max samples to process (None = all)
        """
        logger.info(f"Starting batch processing")

        # Collect samples
        samples = []
        sample_iter = data_loader.iterate_samples()

        for sample in tqdm(sample_iter, desc="Loading samples"):
            if load_images and "url" in sample:
                try:
                    sample["image"] = data_loader.load_image_from_url(sample["url"])
                except Exception as e:
                    logger.warning(f"Failed to load image {sample['url']}: {e}")
                    continue

            samples.append(sample)

            if max_samples and len(samples) >= max_samples:
                break

        logger.info(f"Loaded {len(samples)} samples")

        # Determine batch size
        if self.batch_size:
            batch_size = self.batch_size
        else:
            # Get from first worker
            batch_size = ray.get(self.workers[0].batch_size.remote())

        # Process in batches
        all_results = []
        futures = []

        for i in tqdm(range(0, len(samples), batch_size), desc="Processing batches"):
            batch = samples[i : i + batch_size]

            # Assign to worker (round-robin)
            worker_idx = (i // batch_size) % self.num_workers
            worker = self.workers[worker_idx]

            # Submit batch
            future = worker.process_batch.remote(batch)
            futures.append(future)

            # Collect results periodically to avoid memory buildup
            if len(futures) >= self.num_workers * 2:
                ready_futures, futures = ray.wait(
                    futures, num_returns=len(futures) // 2
                )
                batch_results = ray.get(ready_futures)
                for results in batch_results:
                    all_results.extend(results)

        # Collect remaining results
        if futures:
            batch_results = ray.get(futures)
            for results in batch_results:
                all_results.extend(results)

        logger.info(f"Processed {len(all_results)} samples")

        # Save results
        self._save_results(all_results, output_writer)

        logger.info(f"Results saved to {output_writer.output_dir}")

    def _save_results(
        self, results: List[Dict[str, Any]], output_writer: UnifiedOutputWriter
    ) -> None:
        """Save results to output.

        Args:
            results: List of result dicts
            output_writer: Output writer
        """
        # Prepare DataFrame
        df_data = []
        for result in results:
            row = {
                "url": result["url"],
                "key": result.get("key", ""),
                "caption": result.get("caption", ""),
                "embedding": result["embedding"],
            }
            # Add metadata columns
            for k, v in result.get("metadata", {}).items():
                row[f"meta_{k}"] = v

            df_data.append(row)

        df = pd.DataFrame(df_data)

        # Write parquet
        output_writer.write_parquet(df, "embeddings.parquet")

        # Write metadata
        metadata = {
            "num_samples": len(results),
            "model": self.model_directory,
            "timestamp": time.time(),
        }
        output_writer.write_json(metadata, "metadata.json")


def main():
    """Main entry point for batch inference."""
    parser = argparse.ArgumentParser(description="Batch Inference Service")
    parser.add_argument(
        "--model_directory", required=True, help="Path to model directory"
    )
    parser.add_argument(
        "--input_dir",
        required=True,
        help="Input directory (s3://bucket/prefix or local path)",
    )
    parser.add_argument(
        "--output_dir",
        required=True,
        help="Output directory (s3://bucket/prefix or local path)",
    )
    parser.add_argument(
        "--num_workers", type=int, default=4, help="Number of parallel workers"
    )
    parser.add_argument(
        "--batch_size",
        type=int,
        default=None,
        help="Batch size (None = model default)",
    )
    parser.add_argument(
        "--max_samples", type=int, default=None, help="Max samples to process"
    )
    parser.add_argument("--config", default=None, help="Path to configuration file")
    parser.add_argument(
        "--env", default="prod", choices=["dev", "prod"], help="Environment"
    )
    parser.add_argument("--aws_region", default="us-east-1", help="AWS region")

    args = parser.parse_args()

    # Load configuration
    if args.config:
        config = load_config(config_path=args.config)
    else:
        config = load_config(env=args.env)

    # Setup logging
    setup_logging(config.logging)
    logger.info("Starting batch inference service")
    logger.info(f"Model: {args.model_directory}")
    logger.info(f"Input: {args.input_dir}")
    logger.info(f"Output: {args.output_dir}")
    logger.info(f"Workers: {args.num_workers}")

    # Initialize Ray
    num_gpus = torch.cuda.device_count()
    logger.info(f"Initializing Ray with {num_gpus} GPUs")
    ray.init(num_gpus=num_gpus)

    try:
        # Create data loader
        data_loader = UnifiedDataLoader(
            input_dir=args.input_dir, aws_region=args.aws_region
        )

        # Create output writer
        output_writer = UnifiedOutputWriter(
            output_dir=args.output_dir, aws_region=args.aws_region
        )

        # Create orchestrator
        orchestrator = BatchInferenceOrchestrator(
            model_directory=args.model_directory,
            config=config,
            num_workers=args.num_workers,
            batch_size=args.batch_size,
        )

        # Process dataset
        orchestrator.process_dataset(
            data_loader=data_loader,
            output_writer=output_writer,
            max_samples=args.max_samples,
        )

        logger.info("Batch inference completed successfully")

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Batch inference failed: {e}", exc_info=True)
        raise
    finally:
        ray.shutdown()
        logger.info("Ray shutdown complete")


if __name__ == "__main__":
    main()
