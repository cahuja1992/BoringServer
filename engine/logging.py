"""Structured logging configuration."""

import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional

from engine.config import LoggingConfig


class JSONFormatter(logging.Formatter):
    """JSON log formatter."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.

        Args:
            record: Log record

        Returns:
            JSON formatted log string
        """
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms
        if hasattr(record, "batch_size"):
            log_data["batch_size"] = record.batch_size

        return json.dumps(log_data)


class PlainFormatter(logging.Formatter):
    """Plain text log formatter."""

    def __init__(self):
        fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        super().__init__(fmt=fmt, datefmt="%Y-%m-%d %H:%M:%S")


def setup_logging(config: Optional[LoggingConfig] = None) -> None:
    """Setup logging configuration.

    Args:
        config: Logging configuration
    """
    if config is None:
        from engine.config import get_config

        config = get_config().logging

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.level))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create handler
    if config.output == "stdout":
        handler = logging.StreamHandler(sys.stdout)
    else:
        handler = logging.FileHandler(config.output)

    # Set formatter
    if config.format == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(PlainFormatter())

    root_logger.addHandler(handler)

    # Set third-party loggers to WARNING
    logging.getLogger("ray").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("transformers").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get logger instance.

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    return logging.getLogger(name)
