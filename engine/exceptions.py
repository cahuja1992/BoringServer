"""Custom exceptions for inference engine."""


class InferenceEngineError(Exception):
    """Base exception for inference engine."""

    pass


class ConfigurationError(InferenceEngineError):
    """Configuration error."""

    pass


class ModelLoadError(InferenceEngineError):
    """Model loading error."""

    pass


class QueueFullError(InferenceEngineError):
    """Queue is full error."""

    def __init__(self, message: str = "Request queue is full", queue_depth: int = 0):
        super().__init__(message)
        self.queue_depth = queue_depth


class InvalidImageError(InferenceEngineError):
    """Invalid image error."""

    pass


class InvalidRequestError(InferenceEngineError):
    """Invalid request error."""

    pass


class InferenceTimeoutError(InferenceEngineError):
    """Inference timeout error."""

    pass


class ModelNotFoundError(InferenceEngineError):
    """Model not found error."""

    pass
