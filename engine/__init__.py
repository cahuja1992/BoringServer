"""Inference engine package.

A production-grade inference engine for serving embedding models
and classifiers with batching, monitoring, and comprehensive testing.
"""

__version__ = "1.0.0"

from engine.config import Config, get_config, load_config, set_config
from engine.exceptions import (
    ConfigurationError,
    InferenceEngineError,
    InvalidImageError,
    InvalidRequestError,
    ModelLoadError,
    ModelNotFoundError,
    QueueFullError,
)
from engine.loader import load_model, validate_model_interface
from engine.logging import get_logger, setup_logging
from engine.queue import RequestQueue
from engine.types import InferenceRequest, InferenceResponse, ModelInfo
from engine.utils import decode_image, get_image_info, resize_image, validate_image_size

__all__ = [
    # Version
    "__version__",
    # Config
    "Config",
    "get_config",
    "load_config",
    "set_config",
    # Exceptions
    "InferenceEngineError",
    "ConfigurationError",
    "ModelLoadError",
    "QueueFullError",
    "InvalidImageError",
    "InvalidRequestError",
    "ModelNotFoundError",
    # Loader
    "load_model",
    "validate_model_interface",
    # Logging
    "setup_logging",
    "get_logger",
    # Queue
    "RequestQueue",
    # Types
    "InferenceRequest",
    "InferenceResponse",
    "ModelInfo",
    # Utils
    "decode_image",
    "validate_image_size",
    "get_image_info",
    "resize_image",
]
