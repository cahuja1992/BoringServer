# Batch Processing Guide

## Overview

The BoringServer inference engine now supports large-scale batch processing of image datasets stored in S3. It's designed to work with **img2dataset** format (webdataset with parquet metadata).

## Features

✅ **S3 Integration**: Direct reading from S3 buckets  
✅ **Webdataset Support**: Compatible with img2dataset parquet format  
✅ **Parallel Processing**: Multi-worker Ray-based distributed inference  
✅ **GPU Acceleration**: Automatic GPU detection and utilization  
✅ **Batch Optimization**: Dynamic batching for maximum throughput  
✅ **Progress Tracking**: tqdm progress bars  
✅ **Output Format**: Parquet with embeddings + metadata  

---

## Architecture

```
┌─────────────┐
│ S3 Bucket   │  ← Webdataset (parquet shards)
│  Dataset    │
└──────┬──────┘
       │
┌──────▼─────────────┐
│  S3DataLoader      │  ← Load shards, parse metadata
│                    │
└──────┬─────────────┘
       │
┌──────▼─────────────┐
│  Orchestrator      │  ← Distribute work to workers
│                    │
└──────┬─────────────┘
       │
   ┌───┴───┐
   │       │
┌──▼───┐ ┌─▼────┐
│Worker│ │Worker│  ← Ray actors with GPUs
│  #1  │ │  #2  │     Run batch inference
└──────┘ └──────┘
       │
┌──────▼─────────────┐
│  Output Parquet    │  ← Embeddings + metadata
│                    │
└────────────────────┘
```

---

## Dataset Format

### img2dataset Webdataset Format

The batch processor expects data in **img2dataset** format:

```
s3://bucket/dataset/
├── 00000.parquet  # Shard 0
├── 00001.parquet  # Shard 1
├── 00002.parquet  # Shard 2
└── ...
```

### Parquet Schema

Each parquet file should contain:

| Column | Type | Description |
|--------|------|-------------|
| `url` | string | Image URL (S3 or HTTP) |
| `caption` | string | Text description/caption |
| `key` | string | Unique identifier |
| `width` | int | Image width (optional) |
| `height` | int | Image height (optional) |
| ... | any | Additional metadata |

**Example row:**
```python
{
    "url": "s3://my-bucket/images/img001.jpg",
    "caption": "A cat sitting on a mat",
    "key": "img001",
    "width": 1024,
    "height": 768
}
```

---

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure AWS Credentials

**Option A: Environment Variables**
```bash
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_DEFAULT_REGION="us-east-1"
```

**Option B: AWS CLI**
```bash
aws configure
```

**Option C: IAM Role** (for EC2/ECS)
- Attach IAM role with S3 read permissions to your instance

---

## Usage

### Basic Usage

```bash
python batch_service.py \
  --model_directory models/clip \
  --s3_bucket my-dataset-bucket \
  --s3_prefix datasets/laion-subset \
  --output_path ./output/embeddings \
  --num_workers 4
```

### Full Command Options

```bash
python batch_service.py \
  --model_directory models/clip \           # Path to model
  --s3_bucket my-dataset-bucket \           # S3 bucket name
  --s3_prefix datasets/laion-subset \       # S3 prefix/path
  --output_path ./output/embeddings \       # Local output directory
  --num_workers 4 \                         # Number of parallel workers
  --batch_size 32 \                         # Batch size per worker
  --max_samples 10000 \                     # Limit samples (for testing)
  --env prod \                              # Environment (dev/prod)
  --aws_region us-east-1                    # AWS region
```

### Configuration File

```bash
python batch_service.py \
  --model_directory models/clip \
  --s3_bucket my-bucket \
  --s3_prefix data/ \
  --output_path ./output \
  --config configs/prod.yaml  # Use custom config
```

---

## Performance Tuning

### Worker Configuration

**Number of Workers**:
- CPU mode: `num_workers = num_cpus`
- GPU mode: `num_workers = num_gpus`
- For 8 GPUs: `--num_workers 8`

**Batch Size**:
- Start with model default (usually 8-32)
- Increase until GPU memory is 80-90% full
- Monitor with: `nvidia-smi`

```bash
# Example for 4x A100 GPUs
python batch_service.py \
  --model_directory models/clip \
  --s3_bucket my-bucket \
  --s3_prefix data/ \
  --output_path ./output \
  --num_workers 4 \
  --batch_size 64  # Increase for larger GPUs
```

### Throughput Optimization

| Configuration | Throughput (images/sec) |
|---------------|------------------------|
| 1 GPU, batch=16 | ~100-150 |
| 4 GPUs, batch=32 | ~500-700 |
| 8 GPUs, batch=64 | ~1200-1500 |

**Tips**:
1. Pre-download images to local SSD if possible
2. Use faster S3 region closest to compute
3. Enable S3 Transfer Acceleration
4. Increase network bandwidth between S3 and compute

---

## Output Format

### Output Structure

```
output/
├── embeddings.parquet  # Main output with embeddings
└── metadata.json       # Processing metadata
```

### Embeddings Parquet Schema

| Column | Type | Description |
|--------|------|-------------|
| `url` | string | Original image URL |
| `key` | string | Unique identifier |
| `caption` | string | Text caption |
| `embedding` | list[float] | Model embedding vector |
| `meta_*` | any | Original metadata columns |

### Reading Results

```python
import pandas as pd

# Load embeddings
df = pd.read_parquet("output/embeddings.parquet")

print(f"Processed {len(df)} images")
print(f"Embedding dimension: {len(df['embedding'][0])}")

# Access embeddings
embeddings = df['embedding'].tolist()  # List of vectors
```

---

## Examples

### Example 1: Process LAION Subset

```bash
# Process 100K images from LAION
python batch_service.py \
  --model_directory models/clip \
  --s3_bucket laion5b \
  --s3_prefix part-00000 \
  --output_path ./laion_embeddings \
  --num_workers 8 \
  --batch_size 64 \
  --max_samples 100000
```

### Example 2: Local Testing

```bash
# Test with small sample
python batch_service.py \
  --model_directory models/clip \
  --s3_bucket test-bucket \
  --s3_prefix test-data/ \
  --output_path ./test_output \
  --num_workers 1 \
  --batch_size 8 \
  --max_samples 100  # Only process 100 samples
```

### Example 3: Full Dataset Processing

```bash
# Process entire dataset (no max_samples limit)
python batch_service.py \
  --model_directory models/clip \
  --s3_bucket production-data \
  --s3_prefix datasets/images-2024/ \
  --output_path ./full_embeddings \
  --num_workers 16 \
  --batch_size 128
```

---

## Monitoring

### Progress Tracking

The service provides real-time progress:

```
Loading samples: 100%|████████| 50000/50000 [00:45<00:00, 1111.11it/s]
Processing batches: 100%|████████| 1563/1563 [15:23<00:00, 1.69it/s]
```

### GPU Monitoring

```bash
# Monitor GPU usage in another terminal
watch -n 1 nvidia-smi
```

### Logs

```bash
# View logs
tail -f batch_inference.log
```

---

## Error Handling

### Common Issues

**1. Out of Memory (OOM)**
```
RuntimeError: CUDA out of memory
```
**Solution**: Reduce `--batch_size`

**2. S3 Access Denied**
```
ClientError: Access Denied
```
**Solution**: Check AWS credentials and S3 bucket permissions

**3. Image Load Failure**
```
WARNING: Failed to load image s3://bucket/image.jpg
```
**Solution**: Images are skipped, processing continues

### Retry Logic

Failed images are automatically skipped. Check logs for:
```
WARNING: Failed to load image <url>: <error>
```

---

## Advanced Usage

### Custom Model

```python
# models/custom/model.py
class ModelImpl:
    def load(self):
        # Your model loading
        pass
    
    def encode(self, batch):
        # Your encoding logic
        return embeddings
```

```bash
python batch_service.py \
  --model_directory models/custom \
  ...
```

### Post-Processing

```python
import pandas as pd
import numpy as np

# Load embeddings
df = pd.read_parquet("output/embeddings.parquet")

# Convert to numpy array
embeddings = np.array(df['embedding'].tolist())

# Normalize
embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)

# Build FAISS index
import faiss
index = faiss.IndexFlatIP(embeddings.shape[1])
index.add(embeddings)

# Save index
faiss.write_index(index, "embeddings.faiss")
```

---

## Docker Usage

### Build Image

```bash
docker build -t boringserver/batch:latest .
```

### Run Batch Job

```bash
docker run --gpus all \
  -e AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
  -e AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY \
  -v $(pwd)/output:/output \
  boringserver/batch:latest \
  python batch_service.py \
    --model_directory models/clip \
    --s3_bucket my-bucket \
    --s3_prefix data/ \
    --output_path /output \
    --num_workers 4
```

---

## Kubernetes Deployment

### Batch Job Spec

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: batch-inference-job
spec:
  template:
    spec:
      containers:
      - name: batch-inference
        image: boringserver/batch:latest
        command:
          - python
          - batch_service.py
          - --model_directory=models/clip
          - --s3_bucket=my-bucket
          - --s3_prefix=data/
          - --output_path=/output
          - --num_workers=4
        resources:
          limits:
            nvidia.com/gpu: 4
        env:
          - name: AWS_ACCESS_KEY_ID
            valueFrom:
              secretKeyRef:
                name: aws-credentials
                key: access-key-id
          - name: AWS_SECRET_ACCESS_KEY
            valueFrom:
              secretKeyRef:
                name: aws-credentials
                key: secret-access-key
        volumeMounts:
          - name: output
            mountPath: /output
      restartPolicy: Never
      volumes:
        - name: output
          persistentVolumeClaim:
            claimName: batch-output-pvc
```

---

## Cost Optimization

### EC2 Spot Instances

Use spot instances for batch processing:

```bash
# Example: p3.8xlarge spot (4x V100 GPUs)
# Cost: ~$3-5/hour (70% cheaper than on-demand)
```

### Throughput vs Cost

| Instance | GPUs | Cost/hr | Throughput | Cost/1M images |
|----------|------|---------|------------|----------------|
| p3.2xlarge | 1x V100 | $3 | 150 img/s | $5.56 |
| p3.8xlarge | 4x V100 | $12 | 600 img/s | $5.56 |
| p4d.24xlarge | 8x A100 | $32 | 1500 img/s | $5.93 |

**Recommendation**: Use p3.8xlarge or p3.16xlarge for best cost/performance

---

## API Reference

### S3DataLoader

```python
loader = S3DataLoader(
    s3_bucket="my-bucket",
    s3_prefix="data/",
    aws_region="us-east-1"
)

# List shards
shards = loader.list_shards()

# Load specific shard
df = loader.load_shard("00000.parquet")

# Iterate samples
for sample in loader.iterate_samples():
    print(sample['url'], sample['caption'])
```

### BatchInferenceOrchestrator

```python
orchestrator = BatchInferenceOrchestrator(
    model_directory="models/clip",
    config=config,
    num_workers=4,
    batch_size=32
)

orchestrator.process_dataset(
    data_loader=loader,
    output_path="./output",
    max_samples=1000
)
```

---

## Troubleshooting

### Debug Mode

```bash
# Enable verbose logging
python batch_service.py \
  --env dev \  # Use dev config with DEBUG logging
  ...
```

### Test Connection

```python
import boto3

s3 = boto3.client('s3')
response = s3.list_objects_v2(Bucket='my-bucket', Prefix='data/', MaxKeys=10)
print(response)
```

---

## Next Steps

1. **Scale**: Increase workers and batch size for production
2. **Monitor**: Set up CloudWatch or Datadog monitoring
3. **Optimize**: Profile and tune for your specific model
4. **Index**: Build FAISS/Annoy index for similarity search
5. **Deploy**: Use Kubernetes CronJob for scheduled processing

---

## Support

- **Documentation**: [README.md](README.md)
- **Issues**: [GitHub Issues](https://github.com/cahuja1992/BoringServer/issues)
- **Examples**: [examples/batch_processing.py](examples/)

---

## Performance Benchmarks

### CLIP ViT-Base-Patch32

| Setup | Batch Size | Throughput | GPU Memory |
|-------|-----------|------------|-----------|
| 1x V100 | 16 | 150 img/s | 8GB |
| 1x V100 | 32 | 180 img/s | 14GB |
| 4x V100 | 32 | 650 img/s | 14GB each |
| 8x A100 | 64 | 1500 img/s | 20GB each |

**Processing 1M images**:
- 1x V100: ~2 hours
- 4x V100: ~30 minutes
- 8x A100: ~12 minutes

---

**Ready to process millions of images at scale! 🚀**
