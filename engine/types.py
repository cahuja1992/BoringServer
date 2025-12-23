"""Enhanced types for inference requests."""

import time
import uuid
from asyncio import Future
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class InferenceRequest:
    """Inference request with metadata."""

    payload: Dict[str, Any]
    future: Future
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    enqueue_ts: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def age_ms(self) -> float:
        """Get request age in milliseconds.

        Returns:
            Age in milliseconds
        """
        return (time.time() - self.enqueue_ts) * 1000

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "request_id": self.request_id,
            "enqueue_ts": self.enqueue_ts,
            "age_ms": self.age_ms(),
            "metadata": self.metadata,
        }


@dataclass
class InferenceResponse:
    """Inference response with metadata."""

    output: Any
    request_id: str
    processing_time_ms: float
    batch_size: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "output": self.output,
            "request_id": self.request_id,
            "processing_time_ms": self.processing_time_ms,
            "batch_size": self.batch_size,
            "metadata": self.metadata,
        }


@dataclass
class ModelInfo:
    """Model information."""

    name: str
    version: Optional[str] = None
    description: Optional[str] = None
    batch_size: int = 16
    batch_wait_s: float = 0.003
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "batch_size": self.batch_size,
            "batch_wait_s": self.batch_wait_s,
            "metadata": self.metadata,
        }
