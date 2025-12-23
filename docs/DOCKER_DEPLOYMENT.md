# Docker Deployment Guide

## Quick Start

### Option 1: Using the Build Script (Recommended)

```bash
# Make the script executable
chmod +x scripts/docker-run.sh

# Build and run
./scripts/docker-run.sh
```

This script will:
1. Build the Docker image
2. Stop any existing containers
3. Start the service
4. Wait for health checks
5. Display all endpoints and commands

### Option 2: Using Docker Compose

```bash
# Start the service
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the service
docker-compose down
```

### Option 3: Manual Docker Commands

```bash
# Build the image
docker build -t inference-engine:latest .

# Run the container (CPU mode)
docker run -d \
  --name inference-engine-cpu \
  -p 8000:8000 \
  -p 9090:9090 \
  -e ENVIRONMENT=prod \
  -e INFERENCE_RAY__NUM_GPUS=0 \
  inference-engine:latest \
  --model_directory models/clip --env prod

# Check logs
docker logs -f inference-engine-cpu

# Stop the container
docker stop inference-engine-cpu
docker rm inference-engine-cpu
```

## Model Information

The service uses **openai/clip-vit-base-patch32**:
- **Size**: ~340 MB (will download on first run)
- **Embedding Dimension**: 512
- **Supports**: CPU and GPU
- **Performance**: ~8 images/batch on CPU, ~16 on GPU

## Testing the Service

### Wait for Service to be Ready

The service takes 1-2 minutes to start as it:
1. Downloads the CLIP model (~340 MB)
2. Loads the model into memory
3. Performs warmup inference

Monitor the logs:
```bash
docker logs -f inference-engine-cpu
```

Look for these messages:
```
Model loaded on cpu
Model loaded: clip-vit-base-patch32 in X.XXs
Service running on http://0.0.0.0:8000
```

### Test Endpoints

```bash
# Health check
curl http://localhost:8000/health

# Readiness check
curl http://localhost:8000/ready

# Service info
curl http://localhost:8000/info

# Metrics
curl http://localhost:9090/metrics
```

### Test Inference

Create a test image:
```python
from PIL import Image
img = Image.new('RGB', (224, 224), color='blue')
img.save('test.jpg')
```

Send inference request:
```bash
curl -X POST http://localhost:8000/infer \
  -F "image=@test.jpg" \
  -F "text=a blue image"
```

Expected response:
```json
{
  "output": [[0.123, -0.456, 0.789, ...]],
  "request_id": "uuid-here",
  "processing_time_ms": 45.2,
  "batch_size": 1,
  "total_time_ms": 50.5
}
```

### Automated Testing

Use the test script:
```bash
chmod +x scripts/test-api.sh
./scripts/test-api.sh
```

## GPU Support

To use GPU (requires NVIDIA Docker runtime):

1. Uncomment the GPU service in `docker-compose.yml`
2. Comment out the CPU service
3. Run:
```bash
docker-compose up -d
```

Or manually:
```bash
docker run -d \
  --name inference-engine-gpu \
  --gpus all \
  -p 8000:8000 \
  -p 9090:9090 \
  -e INFERENCE_RAY__NUM_GPUS=1 \
  inference-engine:latest \
  --model_directory models/clip --env prod
```

## Configuration

### Environment Variables

Override configuration via environment variables:

```bash
docker run -d \
  -e INFERENCE_SERVICE__PORT=9000 \
  -e INFERENCE_LOGGING__LEVEL=DEBUG \
  -e INFERENCE_SERVER__MAX_QUEUE_SIZE=2048 \
  -e INFERENCE_RAY__NUM_GPUS=0 \
  inference-engine:latest
```

### Custom Configuration File

Mount a custom config:
```bash
docker run -d \
  -v $(pwd)/custom-config.yaml:/app/configs/custom.yaml \
  inference-engine:latest \
  --config /app/configs/custom.yaml --model_directory models/clip
```

## Troubleshooting

### Container won't start

Check logs:
```bash
docker logs inference-engine-cpu
```

Common issues:
- **Port already in use**: Change port mapping `-p 8001:8000`
- **Out of memory**: Reduce batch size in config
- **Model download fails**: Check internet connection

### Service not responding

1. Check if container is running:
```bash
docker ps | grep inference-engine
```

2. Check health status:
```bash
curl http://localhost:8000/health
```

3. Inspect logs:
```bash
docker logs --tail 100 inference-engine-cpu
```

### Slow performance

- **CPU mode is slower**: Expected, use GPU for production
- **Increase batch size**: Modify config for better throughput
- **Check resources**: Ensure enough RAM available

### Model download issues

If model download fails:
1. Check internet connectivity
2. Try pulling manually:
```bash
docker exec -it inference-engine-cpu bash
python3 -c "from transformers import CLIPModel; CLIPModel.from_pretrained('openai/clip-vit-base-patch32')"
```

## Production Deployment

### Resource Requirements

**Minimum (CPU)**:
- CPU: 2 cores
- RAM: 4 GB
- Disk: 2 GB (for model)

**Recommended (CPU)**:
- CPU: 4 cores
- RAM: 8 GB
- Disk: 5 GB

**With GPU**:
- GPU: NVIDIA with 4+ GB VRAM
- RAM: 8 GB
- CUDA: 11.8+

### Scaling

**Horizontal Scaling**:
```bash
# Run multiple instances on different ports
docker run -d -p 8001:8000 --name engine-1 inference-engine:latest
docker run -d -p 8002:8000 --name engine-2 inference-engine:latest
docker run -d -p 8003:8000 --name engine-3 inference-engine:latest
```

**Load Balancing**:
Use nginx, HAProxy, or cloud load balancer to distribute traffic.

### Monitoring

**Prometheus Integration**:
```yaml
scrape_configs:
  - job_name: 'inference-engine'
    static_configs:
      - targets: ['localhost:9090']
```

**Grafana Dashboards**:
- Request rate and latency
- Queue depth over time
- Batch size distribution
- Error rates by type

### Health Checks

Configure health checks in your orchestrator:

**Docker Compose**:
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 120s
```

**Kubernetes**:
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 120
  periodSeconds: 30

readinessProbe:
  httpGet:
    path: /ready
    port: 8000
  initialDelaySeconds: 60
  periodSeconds: 10
```

## Performance Tuning

### Batch Configuration

Edit `configs/prod.yaml`:
```yaml
models:
  default_batch_size: 8  # Increase for better throughput
  default_batch_wait_s: 0.01  # Increase to accumulate larger batches
```

### Queue Size

For high-traffic scenarios:
```yaml
server:
  max_queue_size: 2048  # Increase to handle bursts
  request_timeout_s: 60  # Increase for slower processing
```

### CPU Threads

Set OMP threads for CPU inference:
```bash
docker run -d \
  -e OMP_NUM_THREADS=4 \
  -e MKL_NUM_THREADS=4 \
  inference-engine:latest
```

## Example Use Cases

### Image Search/Similarity

```bash
# Get embeddings for multiple images
for img in image1.jpg image2.jpg image3.jpg; do
  curl -X POST http://localhost:8000/infer \
    -F "image=@$img" \
    | jq '.output'
done
```

### Content Moderation

```bash
# Check if image matches description
curl -X POST http://localhost:8000/infer \
  -F "image=@user_upload.jpg" \
  -F "text=inappropriate content"
```

### Image Classification

```bash
# Get embeddings and compare with class embeddings
curl -X POST http://localhost:8000/infer \
  -F "image=@photo.jpg" \
  -F "text=cat dog bird car"
```

## Next Steps

1. **Deploy to Kubernetes**: See `docs/kubernetes.md` (create if needed)
2. **Set up monitoring**: Configure Prometheus + Grafana
3. **Add caching**: Redis for frequently requested images
4. **Implement authentication**: Add API keys or OAuth
5. **Enable HTTPS**: Use nginx or cloud load balancer
