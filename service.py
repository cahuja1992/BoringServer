"""Production-grade inference service."""

import argparse
import asyncio
import os
import subprocess
import time
from contextlib import asynccontextmanager
from typing import Optional

import ray
import torch
import uvicorn
from fastapi import FastAPI, File, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from ray import serve

from engine.config import Config, get_config, load_config
from engine.exceptions import (
    InvalidImageError,
    InvalidRequestError,
    ModelLoadError,
    QueueFullError,
)
from engine.loader import load_model, validate_model_interface
from engine.logging import get_logger, setup_logging
from engine.metrics import MetricsCollector, get_metrics
from engine.queue import RequestQueue
from engine.types import InferenceRequest, InferenceResponse
from engine.utils import decode_image, get_image_info, validate_image_size


# Parse arguments
parser = argparse.ArgumentParser(description="Inference Engine Service")
parser.add_argument("--model_directory", required=True, help="Path to model directory")
parser.add_argument(
    "--config", default=None, help="Path to configuration file"
)
parser.add_argument(
    "--env", default="dev", choices=["dev", "prod"], help="Environment (dev/prod)"
)
args = parser.parse_args()

# Load configuration
if args.config:
    config = load_config(config_path=args.config)
else:
    config = load_config(env=args.env)

# Setup logging
setup_logging(config.logging)
logger = get_logger(__name__)


@serve.deployment(
    ray_actor_options={
        "num_gpus": config.ray.num_gpus,
    }
)
class ModelWorker:
    """Model worker for inference."""

    def __init__(self, model_directory: str, config: Config):
        """Initialize model worker.

        Args:
            model_directory: Path to model directory
            config: Service configuration
        """
        self.config = config
        self.model_directory = model_directory
        self.metrics = None
        self.model = None
        self.model_info = None
        self.queue = None
        self.batch_size = config.models.default_batch_size
        self.batch_wait = config.models.default_batch_wait_s
        self._scheduler_task = None

        logger.info(f"Initializing ModelWorker for {model_directory}")

        # Load model
        try:
            start_time = time.time()
            self.model_info, self.model = load_model(model_directory)
            load_duration = time.time() - start_time

            # Validate interface
            validate_model_interface(self.model)

            # Initialize metrics
            self.metrics = MetricsCollector(self.model_info.name)
            self.metrics.record_model_load(load_duration)

            logger.info(
                f"Model loaded: {self.model_info.name} in {load_duration:.2f}s"
            )

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
            self.batch_wait = self.model.batch_wait_s()

            logger.info(
                f"Batch config: size={self.batch_size}, wait={self.batch_wait}s"
            )

        except Exception as e:
            logger.error(f"Failed to initialize model: {e}", exc_info=True)
            raise

        # Initialize queue
        self.queue = RequestQueue(maxsize=config.server.max_queue_size)

        # Start scheduler
        self._scheduler_task = asyncio.create_task(self._scheduler())
        logger.info("ModelWorker initialized successfully")

    async def _scheduler(self) -> None:
        """Background scheduler for batch processing."""
        logger.info("Scheduler started")

        while True:
            try:
                batch_start = time.time()
                batch = await self.queue.get_batch(self.batch_size, self.batch_wait)

                if not batch:
                    continue

                batch_wait_time = time.time() - batch_start

                # Update queue metrics
                self.metrics.update_queue_depth(self.queue.depth())
                self.metrics.record_batch(len(batch), batch_wait_time)

                logger.debug(
                    f"Processing batch: size={len(batch)}, "
                    f"wait_time={batch_wait_time*1000:.2f}ms"
                )

                # Process batch
                process_start = time.time()
                try:
                    outputs = self.model.encode([r.payload for r in batch])
                    process_duration = time.time() - process_start

                    # Set results
                    for req, output in zip(batch, outputs):
                        processing_time = (time.time() - req.enqueue_ts) * 1000
                        response = InferenceResponse(
                            output=output,
                            request_id=req.request_id,
                            processing_time_ms=processing_time,
                            batch_size=len(batch),
                        )
                        req.future.set_result(response)

                        # Record metrics
                        self.metrics.record_request("success", processing_time / 1000)

                    logger.info(
                        f"Batch processed: size={len(batch)}, "
                        f"duration={process_duration*1000:.2f}ms"
                    )

                except Exception as e:
                    logger.error(f"Batch processing failed: {e}", exc_info=True)

                    # Set error for all requests in batch
                    for req in batch:
                        if not req.future.done():
                            req.future.set_exception(e)
                            self.metrics.record_error("processing_error")

            except Exception as e:
                logger.error(f"Scheduler error: {e}", exc_info=True)
                await asyncio.sleep(0.1)

    async def infer(self, request: InferenceRequest) -> InferenceResponse:
        """Process inference request.

        Args:
            request: Inference request

        Returns:
            Inference response

        Raises:
            QueueFullError: If queue is full
            TimeoutError: If request times out
        """
        try:
            await self.queue.put(request)

            # Wait for result with timeout
            result = await asyncio.wait_for(
                request.future,
                timeout=self.config.server.request_timeout_s,
            )

            return result

        except QueueFullError:
            self.metrics.record_queue_rejection()
            raise
        except asyncio.TimeoutError:
            logger.error(f"Request timeout: {request.request_id}")
            self.metrics.record_error("timeout")
            raise HTTPException(status_code=504, detail="Request timeout")
        except Exception as e:
            logger.error(f"Inference error: {e}", exc_info=True)
            self.metrics.record_error("unknown")
            raise

    def get_model_info(self) -> dict:
        """Get model information.

        Returns:
            Model info dictionary
        """
        return self.model_info.to_dict()

    def get_queue_metrics(self) -> dict:
        """Get queue metrics.

        Returns:
            Queue metrics dictionary
        """
        return self.queue.get_metrics()


# Create FastAPI app
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting inference service")
    yield
    logger.info("Shutting down inference service")


app = FastAPI(
    title="Inference Engine",
    description="Production-grade inference engine for embedding models",
    version=config.service.version,
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@serve.deployment
@serve.ingress(app)
class API:
    """API deployment for inference service."""

    def __init__(self, worker: ModelWorker, config: Config):
        """Initialize API.

        Args:
            worker: Model worker
            config: Service configuration
        """
        self.worker = worker
        self.config = config
        logger.info("API initialized")

    @app.post("/infer")
    async def infer(
        self,
        image: UploadFile = File(...),
        text: Optional[str] = None,
    ) -> dict:
        """Perform inference on image and optional text.

        Args:
            image: Image file
            text: Optional text input

        Returns:
            Inference result

        Raises:
            HTTPException: On validation or processing errors
        """
        request_start = time.time()

        try:
            # Validate file
            if not image.content_type or not image.content_type.startswith("image/"):
                raise InvalidRequestError(f"Invalid content type: {image.content_type}")

            # Check file size
            content = await image.read()
            size_mb = len(content) / (1024 * 1024)
            if size_mb > self.config.security.max_upload_size_mb:
                raise InvalidRequestError(
                    f"File too large: {size_mb:.2f}MB "
                    f"(max: {self.config.security.max_upload_size_mb}MB)"
                )

            # Decode image
            img = decode_image(content)

            # Validate image
            validate_image_size(img, self.config.security.max_upload_size_mb)

            # Create payload
            payload = {
                "image": img,
                "text": text,
            }

            # Create request
            future = asyncio.get_event_loop().create_future()
            inference_req = InferenceRequest(
                payload=payload,
                future=future,
                metadata={"image_info": get_image_info(img)},
            )

            # Process request
            response = await self.worker.infer.remote(inference_req)

            duration = time.time() - request_start

            return {
                "output": response.output,
                "request_id": response.request_id,
                "processing_time_ms": response.processing_time_ms,
                "batch_size": response.batch_size,
                "total_time_ms": duration * 1000,
            }

        except InvalidImageError as e:
            logger.warning(f"Invalid image: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except InvalidRequestError as e:
            logger.warning(f"Invalid request: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except QueueFullError as e:
            logger.warning(f"Queue full: {e}")
            raise HTTPException(status_code=429, detail=str(e))
        except Exception as e:
            logger.error(f"Inference error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Internal server error")

    @app.get("/health")
    async def health() -> dict:
        """Health check endpoint.

        Returns:
            Health status
        """
        return {
            "status": "healthy",
            "service": config.service.name,
            "version": config.service.version,
        }

    @app.get("/ready")
    async def ready(self) -> dict:
        """Readiness check endpoint.

        Returns:
            Readiness status
        """
        try:
            model_info = await self.worker.get_model_info.remote()
            return {
                "status": "ready",
                "model": model_info,
            }
        except Exception as e:
            logger.error(f"Readiness check failed: {e}")
            raise HTTPException(status_code=503, detail="Service not ready")

    @app.get("/metrics")
    async def metrics() -> Response:
        """Prometheus metrics endpoint.

        Returns:
            Metrics in Prometheus format
        """
        if not config.metrics.enabled:
            raise HTTPException(status_code=404, detail="Metrics disabled")

        metrics_data = get_metrics()
        return Response(content=metrics_data, media_type="text/plain")

    @app.get("/info")
    async def info(self) -> dict:
        """Get service information.

        Returns:
            Service info
        """
        try:
            model_info = await self.worker.get_model_info.remote()
            queue_metrics = await self.worker.get_queue_metrics.remote()

            return {
                "service": {
                    "name": config.service.name,
                    "version": config.service.version,
                },
                "model": model_info,
                "queue": queue_metrics,
            }
        except Exception as e:
            logger.error(f"Failed to get info: {e}")
            raise HTTPException(status_code=500, detail="Failed to get info")


def main() -> None:
    """Main entry point."""
    logger.info(f"Starting {config.service.name} v{config.service.version}")
    logger.info(f"Model directory: {args.model_directory}")
    logger.info(f"Environment: {args.env}")
    logger.info(f"Configuration: {config.model_dump()}")

    try:
        # Stop any existing Ray instance
        subprocess.run(
            ["ray", "stop", "--force"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Initialize Ray
        logger.info("Initializing Ray")
        ray.init(
            num_gpus=torch.cuda.device_count(),
            include_dashboard=config.ray.include_dashboard,
            log_to_driver=config.ray.log_to_driver,
        )

        # Start Ray Serve
        logger.info("Starting Ray Serve")
        serve.start(detached=True)

        # Deploy service
        logger.info("Deploying service")
        worker = ModelWorker.bind(args.model_directory, config)
        api = API.bind(worker, config)
        serve.run(api, host=config.service.host, port=config.service.port)

        logger.info(
            f"Service running on http://{config.service.host}:{config.service.port}"
        )

    except KeyboardInterrupt:
        logger.info("Shutting down gracefully")
    except Exception as e:
        logger.error(f"Failed to start service: {e}", exc_info=True)
        raise
    finally:
        logger.info("Service stopped")


if __name__ == "__main__":
    main()
