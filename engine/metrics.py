"""Metrics collection and export."""

import time
from typing import Dict

from prometheus_client import Counter, Gauge, Histogram, generate_latest

# Request metrics
request_counter = Counter(
    "inference_requests_total",
    "Total number of inference requests",
    ["model", "status"],
)

request_duration = Histogram(
    "inference_request_duration_seconds",
    "Request processing duration in seconds",
    ["model"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# Batch metrics
batch_size_histogram = Histogram(
    "inference_batch_size",
    "Batch size distribution",
    ["model"],
    buckets=(1, 2, 4, 8, 16, 32, 64, 128),
)

batch_wait_time = Histogram(
    "inference_batch_wait_seconds",
    "Time waiting to form batch",
    ["model"],
    buckets=(0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5),
)

# Queue metrics
queue_depth = Gauge("inference_queue_depth", "Current queue depth", ["model"])

queue_rejections = Counter(
    "inference_queue_rejections_total",
    "Total number of rejected requests due to full queue",
    ["model"],
)

# Model metrics
model_load_time = Gauge(
    "inference_model_load_seconds",
    "Time taken to load model",
    ["model"],
)

model_warmup_time = Gauge(
    "inference_model_warmup_seconds",
    "Time taken to warmup model",
    ["model"],
)

# Error metrics
error_counter = Counter(
    "inference_errors_total",
    "Total number of errors",
    ["model", "error_type"],
)


class MetricsCollector:
    """Metrics collector for inference engine."""

    def __init__(self, model_name: str):
        """Initialize metrics collector.

        Args:
            model_name: Name of the model
        """
        self.model_name = model_name

    def record_request(self, status: str, duration: float) -> None:
        """Record request metrics.

        Args:
            status: Request status (success, error, timeout)
            duration: Request duration in seconds
        """
        request_counter.labels(model=self.model_name, status=status).inc()
        request_duration.labels(model=self.model_name).observe(duration)

    def record_batch(self, size: int, wait_time: float) -> None:
        """Record batch metrics.

        Args:
            size: Batch size
            wait_time: Time waited to form batch
        """
        batch_size_histogram.labels(model=self.model_name).observe(size)
        batch_wait_time.labels(model=self.model_name).observe(wait_time)

    def update_queue_depth(self, depth: int) -> None:
        """Update queue depth metric.

        Args:
            depth: Current queue depth
        """
        queue_depth.labels(model=self.model_name).set(depth)

    def record_queue_rejection(self) -> None:
        """Record queue rejection."""
        queue_rejections.labels(model=self.model_name).inc()

    def record_model_load(self, duration: float) -> None:
        """Record model load time.

        Args:
            duration: Load duration in seconds
        """
        model_load_time.labels(model=self.model_name).set(duration)

    def record_model_warmup(self, duration: float) -> None:
        """Record model warmup time.

        Args:
            duration: Warmup duration in seconds
        """
        model_warmup_time.labels(model=self.model_name).set(duration)

    def record_error(self, error_type: str) -> None:
        """Record error.

        Args:
            error_type: Type of error
        """
        error_counter.labels(model=self.model_name, error_type=error_type).inc()


def get_metrics() -> bytes:
    """Get Prometheus metrics in text format.

    Returns:
        Metrics in Prometheus text format
    """
    return generate_latest()
