"""Create test webdataset in img2dataset format for batch processing.

This script creates a sample parquet dataset compatible with the batch service.
"""

import argparse
import pandas as pd
from pathlib import Path


def create_sample_dataset(output_dir: str, num_samples: int = 100):
    """Create sample parquet dataset.
    
    Args:
        output_dir: Output directory
        num_samples: Number of samples per shard
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    print(f"Creating sample dataset: {num_samples} samples")
    
    # Sample data
    data = []
    for i in range(num_samples):
        sample = {
            "url": f"s3://sample-bucket/images/img_{i:05d}.jpg",
            "caption": f"Sample image {i}: A test image for batch processing",
            "key": f"img_{i:05d}",
            "width": 512,
            "height": 512,
            "source": "synthetic",
        }
        data.append(sample)
    
    # Create DataFrame
    df = pd.DataFrame(data)
    
    # Save as parquet (single shard for testing)
    output_file = output_path / "00000.parquet"
    df.to_parquet(output_file, index=False)
    
    print(f"✓ Created {output_file}")
    print(f"  Rows: {len(df)}")
    print(f"  Columns: {list(df.columns)}")
    print(f"\nSample row:")
    print(df.iloc[0].to_dict())
    
    # Create metadata file
    metadata = {
        "num_shards": 1,
        "num_samples": num_samples,
        "format": "img2dataset",
        "columns": list(df.columns),
    }
    
    import json
    metadata_file = output_path / "metadata.json"
    with open(metadata_file, "w") as f:
        json.dump(metadata, f, indent=2)
    
    print(f"\n✓ Created {metadata_file}")
    print(f"\nDataset ready at: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create sample webdataset")
    parser.add_argument(
        "--output_dir",
        default="./test_dataset",
        help="Output directory for dataset"
    )
    parser.add_argument(
        "--num_samples",
        type=int,
        default=100,
        help="Number of samples to generate"
    )
    
    args = parser.parse_args()
    create_sample_dataset(args.output_dir, args.num_samples)
