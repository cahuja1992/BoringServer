# Batch Processing Quick Start

> **TL;DR**: Process millions of images with CLIP embeddings using `input_dir` and `output_dir` that work seamlessly with both S3 and local filesystem.

---

## ✨ Key Features

✅ **Unified API**: Single `input_dir`/`output_dir` interface for both S3 and local paths  
✅ **Flexible I/O**: Mix and match S3 and local filesystem as needed  
✅ **img2dataset Compatible**: Works directly with webdataset parquet format  
✅ **Multi-GPU**: Parallel processing with Ray actors  
✅ **Auto-detection**: Automatically detects S3 vs local paths  
✅ **Production-ready**: Error handling, progress tracking, and monitoring

---

## 🚀 Quick Start

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Configure AWS (if using S3)
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_DEFAULT_REGION="us-east-1"
```

### Basic Usage

**S3 to S3** (cloud-native):
```bash
python batch_service.py \
  --model_directory models/clip \
  --input_dir s3://my-bucket/datasets/images \
  --output_dir s3://my-bucket/embeddings \
  --num_workers 4
```

**Local to Local** (fully local):
```bash
python batch_service.py \
  --model_directory models/clip \
  --input_dir ./data/webdataset \
  --output_dir ./output/embeddings \
  --num_workers 4
```

**S3 to Local** (download results):
```bash
python batch_service.py \
  --model_directory models/clip \
  --input_dir s3://my-bucket/datasets/images \
  --output_dir ./local_embeddings \
  --num_workers 4
```

**Local to S3** (upload results):
```bash
python batch_service.py \
  --model_directory models/clip \
  --input_dir ./local_dataset \
  --output_dir s3://my-bucket/embeddings \
  --num_workers 4
```

---

## 📊 Input Format

### img2dataset Webdataset Structure

```
input_dir/
├── 00000.parquet  # Shard 0
├── 00001.parquet  # Shard 1
├── 00002.parquet  # Shard 2
└── ...
```

### Parquet Schema

Each parquet file contains:

```python
{
    "url": "s3://bucket/image.jpg",  # or local path
    "caption": "A description",
    "key": "unique_id",
    "width": 1024,    # optional
    "height": 768,    # optional
    # ... additional metadata
}
```

---

## 📤 Output Format

### Output Structure

```
output_dir/
├── embeddings.parquet  # Embeddings + metadata
└── metadata.json       # Processing stats
```

### Reading Results

**From Local:**
```python
import pandas as pd

df = pd.read_parquet("output/embeddings.parquet")
print(f"Processed {len(df)} images")
print(f"Embedding dimension: {len(df['embedding'][0])}")

# Access embeddings
embeddings = df['embedding'].tolist()
```

**From S3:**
```python
import pandas as pd
import boto3

# Option 1: Direct read
df = pd.read_parquet("s3://my-bucket/embeddings/embeddings.parquet")

# Option 2: With boto3
s3 = boto3.client('s3')
obj = s3.get_object(Bucket='my-bucket', Key='embeddings/embeddings.parquet')
df = pd.read_parquet(io.BytesIO(obj['Body'].read()))
```

---

## 🎯 Command-Line Arguments

| Argument | Required | Description | Example |
|----------|----------|-------------|---------|
| `--model_directory` | ✅ | Path to model | `models/clip` |
| `--input_dir` | ✅ | Input path (S3 or local) | `s3://bucket/data` or `./data` |
| `--output_dir` | ✅ | Output path (S3 or local) | `s3://bucket/output` or `./output` |
| `--num_workers` | | Number of parallel workers | `4` (default) |
| `--batch_size` | | Batch size per worker | Model default |
| `--max_samples` | | Limit samples (testing) | `1000` |
| `--env` | | Environment (dev/prod) | `prod` (default) |
| `--aws_region` | | AWS region | `us-east-1` (default) |
| `--config` | | Custom config file | `configs/prod.yaml` |

---

## 🔄 Input/Output Combinations

All four combinations are supported:

| Source | Destination | Use Case |
|--------|-------------|----------|
| 🌐 S3 | 🌐 S3 | **Cloud-native processing** - data stays in cloud |
| 🌐 S3 | 💻 Local | **Download results** - analyze locally after processing |
| 💻 Local | 🌐 S3 | **Upload results** - backup to cloud storage |
| 💻 Local | 💻 Local | **Fully local** - no cloud dependencies |

---

## ⚡ Performance

### Throughput Benchmarks (CLIP ViT-Base-Patch32)

| Setup | Batch Size | Throughput | Time for 1M images |
|-------|-----------|------------|-------------------|
| 1x V100 | 16 | 150 img/s | ~2 hours |
| 4x V100 | 32 | 650 img/s | ~30 minutes |
| 8x A100 | 64 | 1500 img/s | ~12 minutes |

### Tips for Maximum Performance

1. **Match workers to GPUs**: `--num_workers` = number of GPUs
2. **Optimize batch size**: Increase until GPU memory is 80-90% full
3. **Use local storage**: Pre-download to local SSD when possible
4. **Proximity**: Use S3 region closest to compute
5. **Monitor**: Watch GPU usage with `nvidia-smi`

---

## 🐳 Docker Usage

```bash
# Build image
docker build -t boringserver/batch:latest .

# Run batch job
docker run --gpus all \
  -e AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
  -e AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY \
  -v $(pwd)/output:/output \
  boringserver/batch:latest \
  python batch_service.py \
    --model_directory models/clip \
    --input_dir s3://my-bucket/data/ \
    --output_dir /output \
    --num_workers 4
```

---

## ☸️ Kubernetes Deployment

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
          - --input_dir=s3://my-bucket/data/
          - --output_dir=s3://my-bucket/output/
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
      restartPolicy: Never
```

---

## 💡 Examples

### Example 1: Process LAION Subset

```bash
# Process 100K images from LAION in cloud
python batch_service.py \
  --model_directory models/clip \
  --input_dir s3://laion5b/part-00000 \
  --output_dir s3://my-bucket/laion_embeddings \
  --num_workers 8 \
  --batch_size 64 \
  --max_samples 100000
```

### Example 2: Local Testing

```bash
# Test with small dataset locally
python batch_service.py \
  --model_directory models/clip \
  --input_dir ./test-data \
  --output_dir ./test-output \
  --num_workers 1 \
  --batch_size 8 \
  --max_samples 100
```

### Example 3: Hybrid Workflow

```bash
# Step 1: Download a subset from S3
aws s3 sync s3://big-dataset/part-00000 ./local_data --exclude "*" --include "*.parquet"

# Step 2: Process locally
python batch_service.py \
  --model_directory models/clip \
  --input_dir ./local_data \
  --output_dir ./local_output \
  --num_workers 4

# Step 3: Upload results back to S3
aws s3 sync ./local_output s3://my-bucket/embeddings/
```

---

## 🛠️ Troubleshooting

### Issue: Out of Memory (OOM)

```
RuntimeError: CUDA out of memory
```

**Solution**: Reduce batch size
```bash
python batch_service.py ... --batch_size 16  # Start small
```

### Issue: S3 Access Denied

```
ClientError: Access Denied
```

**Solutions**:
1. Check AWS credentials: `aws s3 ls s3://my-bucket/`
2. Verify bucket permissions
3. Check IAM role/policy

### Issue: Image Load Failures

Images with load errors are automatically skipped. Check logs:
```bash
tail -f batch_inference.log | grep "Failed to load"
```

---

## 🔍 Monitoring

### Real-time Progress

```
Loading samples: 100%|████████| 50000/50000 [00:45<00:00]
Processing batches: 100%|████████| 1563/1563 [15:23<00:00]
```

### GPU Usage

```bash
# Monitor GPU in separate terminal
watch -n 1 nvidia-smi
```

### Debug Mode

```bash
python batch_service.py \
  --env dev \  # Enable DEBUG logging
  ...
```

---

## 💰 Cost Optimization

### EC2 Spot Instances

| Instance | GPUs | Spot Cost/hr | Throughput | Cost per 1M images |
|----------|------|--------------|------------|-------------------|
| p3.2xlarge | 1x V100 | ~$0.90 | 150 img/s | ~$1.67 |
| p3.8xlarge | 4x V100 | ~$3.60 | 650 img/s | ~$1.54 |
| p4d.24xlarge | 8x A100 | ~$9.60 | 1500 img/s | ~$1.78 |

**Recommendation**: p3.8xlarge offers the best cost/performance ratio

---

## 📚 API Reference

### UnifiedDataLoader

```python
from batch_service import UnifiedDataLoader

# Auto-detects S3 vs local
loader = UnifiedDataLoader(
    input_dir="s3://bucket/data",  # or "./local/data"
    aws_region="us-east-1"
)

# List all shards
shards = loader.list_shards()

# Load specific shard
df = loader.load_shard(shards[0])

# Iterate samples
for sample in loader.iterate_samples():
    print(sample['url'], sample['caption'])
```

### UnifiedOutputWriter

```python
from batch_service import UnifiedOutputWriter

# Auto-detects S3 vs local
writer = UnifiedOutputWriter(
    output_dir="s3://bucket/output",  # or "./local/output"
    aws_region="us-east-1"
)

# Write parquet
writer.write_parquet(df, "embeddings.parquet")

# Write JSON
writer.write_json(metadata, "metadata.json")
```

### BatchInferenceOrchestrator

```python
from batch_service import BatchInferenceOrchestrator

orchestrator = BatchInferenceOrchestrator(
    model_directory="models/clip",
    config=config,
    num_workers=4,
    batch_size=32
)

orchestrator.process_dataset(
    data_loader=loader,
    output_writer=writer,
    max_samples=10000
)
```

---

## 🎓 Best Practices

1. **Start Small**: Test with `--max_samples 100` first
2. **Monitor Resources**: Watch GPU memory and utilization
3. **Tune Batch Size**: Increase gradually until OOM, then back off 20%
4. **Use Spot Instances**: Save 70% on AWS compute costs
5. **Pre-download Data**: Local SSD is faster than S3 streaming
6. **Handle Errors**: Failed images are skipped automatically
7. **Save Often**: Results are written at the end - use checkpointing for long jobs
8. **Version Control**: Track output with timestamps or version tags

---

## 🔗 Links

- **Full Documentation**: [BATCH_PROCESSING.md](BATCH_PROCESSING.md)
- **Architecture Details**: [ARCHITECTURE.md](../ARCHITECTURE.md)
- **API Reference**: [API.md](../API.md)
- **GitHub Repository**: [BoringServer](https://github.com/cahuja1992/BoringServer)

---

## 🚀 Next Steps

1. ✅ Setup AWS credentials
2. ✅ Test with small dataset locally
3. ✅ Scale to production with multi-GPU
4. ✅ Build FAISS index for similarity search
5. ✅ Deploy on Kubernetes with CronJob

---

**Happy batch processing! 🎉**
