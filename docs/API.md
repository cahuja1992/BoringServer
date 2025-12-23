# API Documentation

## Overview

The Inference Engine provides a REST API for performing inference on images with optional text inputs using embedding models and classifiers.

## Base URL

```
http://localhost:8000
```

## Authentication

Currently, no authentication is required. For production deployments, consider adding:
- API keys
- OAuth2
- JWT tokens

## Endpoints

### POST /infer

Perform inference on an image with optional text.

**Request**

- Method: `POST`
- Content-Type: `multipart/form-data`

**Parameters**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| image | File | Yes | Image file (JPEG, PNG, etc.) |
| text | String | No | Optional text input |

**Example Request**

```bash
curl -X POST http://localhost:8000/infer \
  -F "image=@/path/to/image.jpg" \
  -F "text=a photo of a cat"
```

**Response**

```json
{
  "output": [[0.1, 0.2, 0.3, ...]],
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "processing_time_ms": 15.5,
  "batch_size": 4,
  "total_time_ms": 20.3
}
```

**Status Codes**

- `200 OK` - Success
- `400 Bad Request` - Invalid image or request
- `429 Too Many Requests` - Queue is full
- `500 Internal Server Error` - Processing error
- `504 Gateway Timeout` - Request timeout

**Error Response**

```json
{
  "detail": "Invalid image format: cannot identify image file"
}
```

---

### GET /health

Health check endpoint for load balancers and monitoring.

**Request**

- Method: `GET`

**Response**

```json
{
  "status": "healthy",
  "service": "inference-engine",
  "version": "1.0.0"
}
```

**Status Codes**

- `200 OK` - Service is healthy

---

### GET /ready

Readiness check endpoint to verify model is loaded.

**Request**

- Method: `GET`

**Response**

```json
{
  "status": "ready",
  "model": {
    "name": "clip-vit-l14",
    "version": "1.0",
    "description": "CLIP ViT-L/14 model",
    "batch_size": 16,
    "batch_wait_s": 0.003,
    "metadata": {}
  }
}
```

**Status Codes**

- `200 OK` - Service is ready
- `503 Service Unavailable` - Service not ready

---

### GET /metrics

Prometheus metrics endpoint.

**Request**

- Method: `GET`

**Response**

Plain text Prometheus metrics format:

```
# HELP inference_requests_total Total number of inference requests
# TYPE inference_requests_total counter
inference_requests_total{model="clip-vit-l14",status="success"} 1234.0

# HELP inference_request_duration_seconds Request processing duration in seconds
# TYPE inference_request_duration_seconds histogram
inference_request_duration_seconds_bucket{le="0.005",model="clip-vit-l14"} 456.0
...
```

**Status Codes**

- `200 OK` - Metrics available
- `404 Not Found` - Metrics disabled

---

### GET /info

Get service and model information.

**Request**

- Method: `GET`

**Response**

```json
{
  "service": {
    "name": "inference-engine",
    "version": "1.0.0"
  },
  "model": {
    "name": "clip-vit-l14",
    "version": "1.0",
    "description": "CLIP ViT-L/14 model",
    "batch_size": 16,
    "batch_wait_s": 0.003,
    "metadata": {}
  },
  "queue": {
    "depth": 5,
    "maxsize": 1024,
    "total_requests": 1234,
    "total_rejections": 10,
    "total_timeouts": 2,
    "utilization": 0.0048828125
  }
}
```

**Status Codes**

- `200 OK` - Info retrieved successfully
- `500 Internal Server Error` - Failed to get info

---

## Rate Limiting

Rate limiting is configurable and enforced per client IP.

Default limits:
- 100 requests per 60 seconds

When rate limit is exceeded:
- Status: `429 Too Many Requests`
- Response: `{"detail": "Request queue is full", "queue_depth": 1024}`

## Error Handling

### Error Response Format

```json
{
  "detail": "Error message here"
}
```

### Common Errors

**400 Bad Request**
- Invalid image format
- File too large
- Missing required parameters

**429 Too Many Requests**
- Queue is full
- Rate limit exceeded

**500 Internal Server Error**
- Model processing error
- Unexpected server error

**504 Gateway Timeout**
- Request exceeded timeout limit (default: 30s)

## Performance

### Batching

Requests are automatically batched for optimal throughput:
- Dynamic batch formation
- Configurable batch size (default: 16)
- Configurable wait time (default: 3ms)

### Timeouts

- Request timeout: 30 seconds (configurable)
- Queue wait timeout: Based on batch wait time

### Limits

- Max upload size: 10 MB (configurable)
- Max queue size: 1024 (configurable)
- Max image dimensions: Unlimited (but affects processing time)

## Monitoring

### Metrics

All endpoints emit Prometheus metrics:
- Request counts by status
- Processing duration histograms
- Queue depth gauges
- Batch size distributions
- Error counts by type

### Logging

All requests are logged with:
- Request ID
- Processing time
- Batch size
- Queue depth
- Status

## Examples

### Python

```python
import requests

# Inference request
with open("image.jpg", "rb") as f:
    files = {"image": f}
    data = {"text": "optional text"}
    response = requests.post(
        "http://localhost:8000/infer",
        files=files,
        data=data
    )
    result = response.json()
    print(result["output"])

# Health check
response = requests.get("http://localhost:8000/health")
print(response.json())
```

### cURL

```bash
# Inference
curl -X POST http://localhost:8000/infer \
  -F "image=@image.jpg" \
  -F "text=optional text"

# Health
curl http://localhost:8000/health

# Metrics
curl http://localhost:8000/metrics

# Info
curl http://localhost:8000/info
```

### JavaScript

```javascript
// Inference request
const formData = new FormData();
formData.append('image', imageFile);
formData.append('text', 'optional text');

const response = await fetch('http://localhost:8000/infer', {
  method: 'POST',
  body: formData
});

const result = await response.json();
console.log(result.output);
```
