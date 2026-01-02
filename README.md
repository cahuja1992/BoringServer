# The Boring Inferencing Engine

[![Docker Hub](https://img.shields.io/docker/v/boringserver/inference-engine?label=Docker%20Hub&logo=docker)](https://hub.docker.com/r/boringserver/inference-engine)
[![Docker Image Size](https://img.shields.io/docker/image-size/boringserver/inference-engine/latest)](https://hub.docker.com/r/boringserver/inference-engine)
[![Docker Pulls](https://img.shields.io/docker/pulls/boringserver/inference-engine)](https://hub.docker.com/r/boringserver/inference-engine)
[![CI/CD](https://github.com/cahuja1992/BoringServer/actions/workflows/docker-hub.yml/badge.svg)](https://github.com/cahuja1992/BoringServer/actions/workflows/docker-hub.yml)

A production-grade inference engine for serving embedding models and classifiers with batching, monitoring, and comprehensive testing.

## Features

### Real-Time Inference
- ⚡ **High Performance**: Dynamic batching with configurable batch sizes and wait times
- 📊 **Monitoring**: Prometheus metrics, structured logging, and health checks
- 🔒 **Production Ready**: Rate limiting, request validation, error handling
- 🧪 **Comprehensive Testing**: Unit tests, integration tests, and code coverage
- 🐳 **Docker Support**: Containerized deployment with GPU support
- ⚙️ **Configurable**: YAML-based configuration with environment overrides
- 🔄 **Async Processing**: Non-blocking request queue with async/await

### Batch Processing
- 🚀 **Large-Scale Processing**: Process millions of images efficiently
- 🌐 **Flexible I/O**: Unified `input_dir`/`output_dir` API for S3 and local filesystem
- 📦 **img2dataset Compatible**: Works directly with webdataset parquet format
- 🔀 **Multi-GPU**: Parallel processing with Ray actors
- 💾 **Smart I/O**: Mix and match S3 and local paths as needed
- 📊 **Production Ready**: Error handling, progress tracking, and monitoring

## Architecture

```
┌─────────────┐
│   FastAPI   │  ← REST API
│     API     │
└──────┬──────┘
       │
┌──────▼──────────┐
│  Model Worker   │  ← Ray Serve Deployment
│   + Scheduler   │
└──────┬──────────┘
       │
┌──────▼──────────┐
│ Request Queue   │  ← Async batching
│   + Metrics     │
└──────┬──────────┘
       │
┌──────▼──────────┐
│  Model (GPU)    │  ← PyTorch/Transformers
│   Inference     │
└─────────────────┘
```

## Quick Start

### Installation

```bash
# Install dependencies
pip install -e ".[dev]"

# Or install without dev dependencies
pip install -e .
```

### Running the Real-Time Service

```bash
# Development mode
python service.py --model_directory models/clip --env dev

# Production mode
python service.py --model_directory models/clip --env prod

# With custom config
python service.py --model_directory models/clip --config configs/custom.yaml
```

### Running Batch Processing

Process large datasets with S3 or local filesystem:

```bash
# S3 to S3 (cloud-native)
python batch_service.py \
  --model_directory models/clip \
  --input_dir s3://my-bucket/datasets/images \
  --output_dir s3://my-bucket/embeddings \
  --num_workers 4

# Local to Local
python batch_service.py \
  --model_directory models/clip \
  --input_dir ./data/webdataset \
  --output_dir ./output/embeddings \
  --num_workers 4

# Mix and match: S3 to Local, Local to S3
python batch_service.py \
  --model_directory models/clip \
  --input_dir s3://my-bucket/data \
  --output_dir ./local_output \
  --num_workers 4
```

**📖 See [Batch Processing Quick Start](docs/BATCH_PROCESSING_QUICKSTART.md) and [Full Guide](docs/BATCH_PROCESSING.md)**

### Environment Variables

```bash
# Set environment
export ENVIRONMENT=prod

# Override specific settings
export INFERENCE_SERVICE__PORT=9000
export INFERENCE_LOGGING__LEVEL=DEBUG
export INFERENCE_CONFIG_PATH=/path/to/config.yaml
```

## API Endpoints

### POST /infer

Perform inference on an image with optional text.

```bash
curl -X POST http://localhost:8000/infer \
  -F "image=@/path/to/image.jpg" \
  -F "text=optional text"
```

Response:
```json
{
  "output": [[0.1, 0.2, 0.3, ...]],
  "request_id": "uuid",
  "processing_time_ms": 15.5,
  "batch_size": 4,
  "total_time_ms": 20.3
}
```

### GET /health

Health check endpoint.

```bash
curl http://localhost:8000/health
```

### GET /ready

Readiness check endpoint.

```bash
curl http://localhost:8000/ready
```

### GET /metrics

Prometheus metrics endpoint.

```bash
curl http://localhost:8000/metrics
```

### GET /info

Service and model information.

```bash
curl http://localhost:8000/info
```

## Configuration

Configuration is managed through YAML files in the `configs/` directory.

### Base Configuration (configs/base.yaml)

```yaml
service:
  name: "inference-engine"
  host: "0.0.0.0"
  port: 8000

ray:
  num_gpus: 1

server:
  max_queue_size: 1024
  request_timeout_s: 30

logging:
  level: "INFO"
  format: "json"
```

### Environment-Specific Configs

- `configs/dev.yaml` - Development settings
- `configs/prod.yaml` - Production settings

## Model Interface

Models must implement the following interface:

```python
class ModelImpl:
    def load(self) -> None:
        """Load model weights and initialize."""
        pass
    
    def warmup(self) -> None:
        """Warmup the model with dummy inputs."""
        pass
    
    def batch_size(self) -> int:
        """Return optimal batch size."""
        return 16
    
    def batch_wait_s(self) -> float:
        """Return max wait time to form batch."""
        return 0.003
    
    def encode(self, batch: List[Dict]) -> List[Any]:
        """Process a batch of inputs.
        
        Args:
            batch: List of dicts with 'image' and optional 'text'
        
        Returns:
            List of outputs (embeddings, logits, etc.)
        """
        pass
```

### Model Directory Structure

```
models/
└── your-model/
    ├── config.json      # Model metadata
    └── model.py         # Model implementation
```

### Example config.json

```json
{
  "name": "clip-vit-l14",
  "version": "1.0",
  "description": "CLIP ViT-L/14 model",
  "batch_size": 16,
  "batch_wait_s": 0.003,
  "metadata": {
    "framework": "pytorch",
    "type": "embedding"
  }
}
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=engine --cov=models --cov-report=html

# Run specific test file
pytest tests/unit/test_queue.py

# Run with verbose output
pytest -v

# Run only unit tests
pytest tests/unit/

# Run only integration tests
pytest tests/integration/
```

### Test Coverage

The project includes comprehensive tests for:

- ✅ Configuration management
- ✅ Request queue and batching
- ✅ Image utilities and validation
- ✅ Model loading and validation
- ✅ Type definitions
- ✅ Exception handling
- ✅ Logging setup
- ⏳ Integration tests (requires GPU)

## Monitoring

### Prometheus Metrics

Available metrics:

- `inference_requests_total` - Total requests by model and status
- `inference_request_duration_seconds` - Request processing time
- `inference_batch_size` - Batch size distribution
- `inference_batch_wait_seconds` - Batch formation wait time
- `inference_queue_depth` - Current queue depth
- `inference_queue_rejections_total` - Rejected requests
- `inference_errors_total` - Errors by type
- `inference_model_load_seconds` - Model load time
- `inference_model_warmup_seconds` - Model warmup time

### Logging

Structured JSON logging with configurable levels:

```json
{
  "timestamp": "2024-01-15T10:30:45.123456",
  "level": "INFO",
  "logger": "engine.queue",
  "message": "Request enqueued",
  "request_id": "abc-123",
  "queue_depth": 5
}
```

## Docker Deployment

### Quick Start with Docker Hub

```bash
# Pull the latest image
docker pull boringserver/inference-engine:latest

# Run with CLIP model (CPU mode)
docker run -p 8000:8000 boringserver/inference-engine:latest

# Run with GPU support
docker run --gpus all -p 8000:8000 boringserver/inference-engine:latest

# Test the API
curl http://localhost:8000/health
```

### Build from Source

```bash
# Build image
docker build -t inference-engine:latest .

# Run container
docker run --gpus all -p 8000:8000 \
  -v $(pwd)/models:/app/models \
  -e ENVIRONMENT=prod \
  inference-engine:latest \
  --model_directory /app/models/clip
```

### Docker Compose

```bash
# Start with docker-compose
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

For detailed Docker deployment instructions, see [DOCKER_DEPLOYMENT.md](docs/DOCKER_DEPLOYMENT.md).

For Docker Hub setup and CI/CD, see [DOCKER_HUB_SETUP.md](docs/DOCKER_HUB_SETUP.md).

## Development

### Setup Development Environment

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Format code
black .
isort .

# Lint
flake8 engine/ tests/
mypy engine/
```

### Code Quality Tools

- **Black**: Code formatting
- **isort**: Import sorting
- **flake8**: Linting
- **mypy**: Type checking
- **pytest**: Testing
- **pre-commit**: Git hooks

## Performance Tips

1. **Batch Size**: Tune `batch_size` based on GPU memory
2. **Batch Wait Time**: Balance latency vs throughput with `batch_wait_s`
3. **Queue Size**: Adjust `max_queue_size` for peak load
4. **GPU Allocation**: Set `num_gpus` appropriately
5. **Workers**: Use multiple workers for CPU-bound preprocessing

## Troubleshooting

### Common Issues

**GPU Out of Memory**
- Reduce batch size in model config
- Check image preprocessing size

**High Latency**
- Increase batch_wait_s for better batching
- Check queue depth metrics

**Queue Full Errors**
- Increase max_queue_size
- Add more workers
- Optimize model performance

## License

MIT License

## Contributing

1. Fork the repository
2. Create a feature branch
3. Write tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## Support

For issues and questions:
- Create an issue on GitHub
- Check documentation in `docs/`
- Review example models in `models/`

## Documentation

### Real-Time Inference
- [Architecture](docs/ARCHITECTURE.md)
- [API Reference](docs/API.md)
- [Docker Deployment](docs/DOCKER_DEPLOYMENT.md)
- [Docker Hub Setup](docs/DOCKER_HUB_SETUP.md)

### Batch Processing
- [Quick Start Guide](docs/BATCH_PROCESSING_QUICKSTART.md) - Get started in 5 minutes
- [Full Documentation](docs/BATCH_PROCESSING.md) - Comprehensive guide with examples
- Supported formats: img2dataset webdataset (parquet shards)
- Flexible I/O: S3 ↔ S3, S3 ↔ Local, Local ↔ Local
- Performance: 150-1500 images/second depending on GPU setup
