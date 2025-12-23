# Quick Start Guide

## Installation

```bash
# Install dependencies
pip install -e ".[dev]"
```

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=engine --cov-report=html

# Open coverage report
open htmlcov/index.html
```

## Running the Service (requires GPU)

```bash
# Development mode
python service.py --model_directory models/clip --env dev

# Production mode  
python service.py --model_directory models/clip --env prod
```

## Using Docker

```bash
# Build image
docker build -t inference-engine:latest .

# Run with GPU
docker run --gpus all -p 8000:8000 \
  -v $(pwd)/models:/app/models \
  inference-engine:latest \
  --model_directory /app/models/clip

# Or use docker-compose
docker-compose up
```

## Testing the API

```bash
# Health check
curl http://localhost:8000/health

# Inference (requires running service)
curl -X POST http://localhost:8000/infer \
  -F "image=@test_image.jpg" \
  -F "text=a photo of a cat"
```

## Development

```bash
# Format code
make format

# Run linters
make lint

# Clean build artifacts
make clean
```

## What to Test

1. **Unit Tests** - Already complete and passing
2. **Code Quality** - Run `make lint` 
3. **Documentation** - Read README.md, ARCHITECTURE.md, API.md

## Next Steps

To deploy this in production:

1. Set environment variables for configuration
2. Configure proper GPU resources
3. Set up Prometheus for metrics collection
4. Configure health check monitoring
5. Set up CI/CD pipeline for your repo

All the infrastructure is ready - just needs your models and deployment environment!
