# Architecture Overview

## Project Structure

```
inference-engine/
├── .github/
│   └── workflows/
│       └── ci.yml                 # GitHub Actions CI/CD pipeline
├── configs/
│   ├── base.yaml                  # Base configuration
│   ├── dev.yaml                   # Development configuration
│   └── prod.yaml                  # Production configuration
├── docs/
│   └── API.md                     # API documentation
├── engine/
│   ├── __init__.py                # Package initialization
│   ├── config.py                  # Configuration management with Pydantic
│   ├── exceptions.py              # Custom exceptions
│   ├── loader.py                  # Model loader with validation
│   ├── logging.py                 # Structured logging (JSON/plain)
│   ├── metrics.py                 # Prometheus metrics collection
│   ├── queue.py                   # Async request queue with monitoring
│   ├── types.py                   # Type definitions (Request/Response/ModelInfo)
│   └── utils.py                   # Image utilities and validation
├── models/
│   ├── clip/
│   │   ├── config.json            # Model configuration
│   │   └── model.py               # CLIP model implementation
│   └── flava_classifier/
│       ├── config.json            # Model configuration
│       └── model.py               # FLAVA classifier implementation
├── tests/
│   ├── __init__.py
│   ├── conftest.py                # Pytest fixtures and configuration
│   ├── integration/
│   │   ├── __init__.py
│   │   └── test_api.py            # Integration tests (requires GPU)
│   └── unit/
│       ├── __init__.py
│       ├── test_config.py         # Configuration tests
│       ├── test_loader.py         # Model loader tests
│       ├── test_queue.py          # Request queue tests
│       ├── test_types.py          # Type definition tests
│       └── test_utils.py          # Utility function tests
├── .gitignore                     # Git ignore rules
├── .pre-commit-config.yaml        # Pre-commit hooks configuration
├── docker-compose.yml             # Docker Compose configuration
├── Dockerfile                     # Docker image definition
├── Makefile                       # Common development tasks
├── pyproject.toml                 # Project metadata and dependencies
├── README.md                      # Project documentation
├── requirements.txt               # Production dependencies
├── requirements-dev.txt           # Development dependencies
└── service.py                     # Main service entry point
```

## Component Architecture

### 1. Service Layer (service.py)

```
FastAPI Application
        ↓
    API Class (Ray Serve Deployment)
        ↓
    ModelWorker (Ray Actor with GPU)
        ↓
    Request Queue + Scheduler
        ↓
    Model Implementation
```

**Key Features:**
- Ray Serve for distributed serving
- FastAPI for REST API
- Async/await for non-blocking operations
- GPU allocation via Ray

### 2. Engine Components

#### Configuration (engine/config.py)
- **Pydantic-based validation**
- **Environment variable overrides**
- **YAML configuration files**
- **Hierarchical config merging**

```python
Config
├── ServiceConfig (name, host, port)
├── RayConfig (num_gpus, dashboard)
├── ServerConfig (queue_size, timeouts)
├── LoggingConfig (level, format)
├── MetricsConfig (enabled, port)
├── HealthConfig (paths)
├── ModelsConfig (batch settings)
└── SecurityConfig (rate limiting)
```

#### Request Queue (engine/queue.py)
- **Async batching** with configurable size and wait time
- **Metrics tracking** (requests, rejections, timeouts)
- **Non-blocking** put/get operations
- **Queue depth monitoring**

#### Model Loader (engine/loader.py)
- **Dynamic model loading** from directories
- **Interface validation** (ensures required methods exist)
- **Configuration parsing** from JSON
- **Error handling** with custom exceptions

#### Metrics (engine/metrics.py)
- **Prometheus integration**
- **Request counters** by status
- **Duration histograms** for latency tracking
- **Batch size distributions**
- **Queue depth gauges**
- **Error counters** by type

#### Logging (engine/logging.py)
- **Structured JSON logging**
- **Configurable log levels**
- **Request ID tracking**
- **Duration and batch size logging**

### 3. Request Flow

```
1. Client → POST /infer with image + text
                 ↓
2. API validates request
   - Check content type
   - Validate file size
   - Decode image
   - Validate dimensions
                 ↓
3. Create InferenceRequest
   - Generate request ID
   - Timestamp enqueue
   - Create async Future
                 ↓
4. Enqueue request
   - Add to RequestQueue
   - Track metrics
   - Handle queue full errors
                 ↓
5. Scheduler batches requests
   - Wait for batch_size OR batch_wait_s
   - Collect multiple requests
   - Update metrics
                 ↓
6. Model processes batch
   - Run inference on GPU
   - Generate embeddings/logits
   - Track processing time
                 ↓
7. Set results on Futures
   - Each request gets its output
   - Record metrics
   - Update queue depth
                 ↓
8. Return response to client
   - output: model results
   - request_id: tracking
   - processing_time_ms: latency
   - batch_size: batching info
```

### 4. Model Interface

Models must implement:

```python
class ModelImpl:
    def load(self) -> None:
        """Load model weights and initialize."""
        
    def warmup(self) -> None:
        """Warmup with dummy inputs."""
        
    def batch_size(self) -> int:
        """Return optimal batch size."""
        
    def batch_wait_s(self) -> float:
        """Return max wait time for batching."""
        
    def encode(self, batch: List[Dict]) -> List[Any]:
        """Process batch and return outputs."""
```

### 5. Observability

#### Metrics (Prometheus)
- `inference_requests_total{model, status}`
- `inference_request_duration_seconds{model}`
- `inference_batch_size{model}`
- `inference_queue_depth{model}`
- `inference_errors_total{model, error_type}`

#### Logs (Structured JSON)
```json
{
  "timestamp": "2024-01-15T10:30:45",
  "level": "INFO",
  "logger": "engine.queue",
  "message": "Batch processed",
  "request_id": "abc-123",
  "batch_size": 8,
  "duration_ms": 15.5
}
```

#### Health Checks
- `/health` - Liveness probe
- `/ready` - Readiness probe (checks model loaded)
- `/metrics` - Prometheus metrics
- `/info` - Service and model information

### 6. Error Handling

```
Exception Hierarchy:
├── InferenceEngineError (base)
    ├── ConfigurationError
    ├── ModelLoadError
    ├── ModelNotFoundError
    ├── QueueFullError
    ├── InvalidImageError
    ├── InvalidRequestError
    └── InferenceTimeoutError
```

**Error Responses:**
- 400: Invalid image/request
- 429: Queue full
- 500: Processing error
- 503: Service not ready
- 504: Request timeout

### 7. Security

- **File size limits** (default: 10MB)
- **Image validation** (format, dimensions)
- **Rate limiting** (configurable per client)
- **Queue size limits** (prevent memory exhaustion)
- **Request timeouts** (prevent hanging)

### 8. Deployment

#### Docker
- CUDA base image for GPU support
- Multi-stage build for optimization
- Non-root user for security
- Health checks built-in

#### Kubernetes (recommended)
- HorizontalPodAutoscaler based on queue depth
- GPU node affinity
- Prometheus ServiceMonitor
- Liveness and readiness probes

## Performance Tuning

### Batch Configuration
- **batch_size**: Balance GPU utilization vs latency
- **batch_wait_s**: Balance throughput vs latency
- Larger batches = higher throughput, higher latency
- Smaller waits = lower latency, lower throughput

### Queue Configuration
- **max_queue_size**: Handle traffic spikes
- Too small = frequent rejections
- Too large = memory issues

### GPU Allocation
- **num_gpus**: Set based on model requirements
- Multiple workers for CPU-bound preprocessing

## Testing Strategy

### Unit Tests
- Configuration management
- Queue operations
- Image utilities
- Model loading
- Type definitions

### Integration Tests
- End-to-end API testing
- Concurrent request handling
- Error scenarios
- Performance benchmarks

### CI/CD
- Automated testing on PRs
- Code quality checks (black, isort, flake8, mypy)
- Coverage reporting
- Docker image builds
