"""Enhanced model loader with validation."""

import json
import os
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any, Dict, Tuple

from engine.exceptions import ConfigurationError, ModelLoadError, ModelNotFoundError
from engine.logging import get_logger
from engine.types import ModelInfo

logger = get_logger(__name__)


def load_model(model_dir: str) -> Tuple[ModelInfo, Any]:
    """Load model from directory.

    Args:
        model_dir: Path to model directory

    Returns:
        Tuple of (ModelInfo, model instance)

    Raises:
        ModelNotFoundError: If model directory doesn't exist
        ConfigurationError: If config.json is invalid
        ModelLoadError: If model.py fails to load
    """
    model_path = Path(model_dir)

    # Validate directory exists
    if not model_path.exists():
        raise ModelNotFoundError(f"Model directory not found: {model_dir}")

    if not model_path.is_dir():
        raise ModelNotFoundError(f"Not a directory: {model_dir}")

    logger.info(f"Loading model from: {model_dir}")

    # Load configuration
    config_path = model_path / "config.json"
    if not config_path.exists():
        raise ConfigurationError(f"config.json not found in {model_dir}")

    try:
        with open(config_path) as f:
            config_data = json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigurationError(f"Invalid config.json: {e}")
    except Exception as e:
        raise ConfigurationError(f"Failed to read config.json: {e}")

    # Validate config
    if not isinstance(config_data, dict):
        raise ConfigurationError("config.json must be a JSON object")

    if "name" not in config_data:
        raise ConfigurationError("config.json must contain 'name' field")

    # Create ModelInfo
    model_info = ModelInfo(
        name=config_data["name"],
        version=config_data.get("version"),
        description=config_data.get("description"),
        batch_size=config_data.get("batch_size", 16),
        batch_wait_s=config_data.get("batch_wait_s", 0.003),
        metadata=config_data.get("metadata", {}),
    )

    logger.info(f"Model config loaded: {model_info.name}")

    # Load model implementation
    model_py_path = model_path / "model.py"
    if not model_py_path.exists():
        raise ModelLoadError(f"model.py not found in {model_dir}")

    try:
        spec = spec_from_file_location("model_impl", str(model_py_path))
        if spec is None or spec.loader is None:
            raise ModelLoadError(f"Failed to load module spec from {model_py_path}")

        module = module_from_spec(spec)
        spec.loader.exec_module(module)

        if not hasattr(module, "ModelImpl"):
            raise ModelLoadError("model.py must define ModelImpl class")

        model_instance = module.ModelImpl()
        logger.info(f"Model implementation loaded: {model_info.name}")

        return model_info, model_instance

    except ModelLoadError:
        raise
    except Exception as e:
        logger.error(f"Failed to load model implementation: {e}")
        raise ModelLoadError(f"Failed to load model.py: {e}")


def validate_model_interface(model: Any) -> None:
    """Validate model implements required interface.

    Args:
        model: Model instance

    Raises:
        ModelLoadError: If model doesn't implement required methods
    """
    required_methods = ["load", "warmup", "batch_size", "batch_wait_s", "encode"]

    for method in required_methods:
        if not hasattr(model, method):
            raise ModelLoadError(f"Model must implement '{method}' method")

        if not callable(getattr(model, method)):
            raise ModelLoadError(f"Model.{method} must be callable")

    logger.debug("Model interface validated")
