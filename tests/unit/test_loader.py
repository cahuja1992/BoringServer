"""Unit tests for model loader."""

import json
import tempfile
from pathlib import Path

import pytest

from engine.exceptions import ConfigurationError, ModelLoadError, ModelNotFoundError
from engine.loader import load_model, validate_model_interface
from engine.types import ModelInfo


class MockModel:
    """Mock model implementation for testing."""

    def load(self):
        """Load model."""
        pass

    def warmup(self):
        """Warmup model."""
        pass

    def batch_size(self):
        """Get batch size."""
        return 16

    def batch_wait_s(self):
        """Get batch wait time."""
        return 0.003

    def encode(self, batch):
        """Encode batch."""
        return [[0.1, 0.2, 0.3] for _ in batch]


class IncompleteModel:
    """Model with missing methods."""

    def load(self):
        """Load model."""
        pass


@pytest.fixture
def temp_model_dir():
    """Create temporary model directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def create_model_files(model_dir, config_data=None, model_code=None):
    """Create model configuration and implementation files.

    Args:
        model_dir: Directory to create files in
        config_data: Configuration dictionary
        model_code: Python code for model.py
    """
    # Create config.json
    if config_data is None:
        config_data = {"name": "test-model"}

    config_path = model_dir / "config.json"
    with open(config_path, "w") as f:
        json.dump(config_data, f)

    # Create model.py
    if model_code is None:
        model_code = """
class ModelImpl:
    def load(self):
        pass
    
    def warmup(self):
        pass
    
    def batch_size(self):
        return 16
    
    def batch_wait_s(self):
        return 0.003
    
    def encode(self, batch):
        return [[0.1, 0.2] for _ in batch]
"""

    model_path = model_dir / "model.py"
    with open(model_path, "w") as f:
        f.write(model_code)


class TestLoadModel:
    """Tests for load_model function."""

    def test_load_valid_model(self, temp_model_dir):
        """Test loading valid model."""
        create_model_files(
            temp_model_dir,
            config_data={"name": "test-model", "version": "1.0"},
        )

        model_info, model = load_model(str(temp_model_dir))

        assert isinstance(model_info, ModelInfo)
        assert model_info.name == "test-model"
        assert model_info.version == "1.0"
        assert model is not None

    def test_load_model_directory_not_found(self):
        """Test error when model directory doesn't exist."""
        with pytest.raises(ModelNotFoundError, match="not found"):
            load_model("/nonexistent/directory")

    def test_load_model_path_is_file(self, temp_model_dir):
        """Test error when path is a file, not directory."""
        file_path = temp_model_dir / "test.txt"
        file_path.write_text("test")

        with pytest.raises(ModelNotFoundError, match="Not a directory"):
            load_model(str(file_path))

    def test_load_model_config_missing(self, temp_model_dir):
        """Test error when config.json is missing."""
        # Only create model.py
        model_path = temp_model_dir / "model.py"
        model_path.write_text("class ModelImpl: pass")

        with pytest.raises(ConfigurationError, match="config.json not found"):
            load_model(str(temp_model_dir))

    def test_load_model_config_invalid_json(self, temp_model_dir):
        """Test error when config.json is invalid JSON."""
        config_path = temp_model_dir / "config.json"
        config_path.write_text("invalid json {")

        with pytest.raises(ConfigurationError, match="Invalid config.json"):
            load_model(str(temp_model_dir))

    def test_load_model_config_not_dict(self, temp_model_dir):
        """Test error when config.json is not a dictionary."""
        config_path = temp_model_dir / "config.json"
        config_path.write_text('["list", "not", "dict"]')

        with pytest.raises(ConfigurationError, match="must be a JSON object"):
            load_model(str(temp_model_dir))

    def test_load_model_config_missing_name(self, temp_model_dir):
        """Test error when config.json doesn't have 'name' field."""
        create_model_files(temp_model_dir, config_data={"version": "1.0"})

        with pytest.raises(ConfigurationError, match="must contain 'name'"):
            load_model(str(temp_model_dir))

    def test_load_model_py_missing(self, temp_model_dir):
        """Test error when model.py is missing."""
        config_path = temp_model_dir / "config.json"
        with open(config_path, "w") as f:
            json.dump({"name": "test"}, f)

        with pytest.raises(ModelLoadError, match="model.py not found"):
            load_model(str(temp_model_dir))

    def test_load_model_no_modelimpl_class(self, temp_model_dir):
        """Test error when model.py doesn't define ModelImpl."""
        create_model_files(
            temp_model_dir,
            model_code="class WrongName: pass",
        )

        with pytest.raises(ModelLoadError, match="must define ModelImpl"):
            load_model(str(temp_model_dir))

    def test_load_model_with_optional_fields(self, temp_model_dir):
        """Test loading model with optional config fields."""
        config_data = {
            "name": "test-model",
            "version": "2.0",
            "description": "Test model",
            "batch_size": 32,
            "batch_wait_s": 0.01,
            "metadata": {"key": "value"},
        }

        create_model_files(temp_model_dir, config_data=config_data)

        model_info, model = load_model(str(temp_model_dir))

        assert model_info.name == "test-model"
        assert model_info.version == "2.0"
        assert model_info.description == "Test model"
        assert model_info.batch_size == 32
        assert model_info.batch_wait_s == 0.01
        assert model_info.metadata == {"key": "value"}

    def test_load_model_with_syntax_error(self, temp_model_dir):
        """Test error when model.py has syntax error."""
        create_model_files(
            temp_model_dir,
            model_code="class ModelImpl:\n    def invalid syntax",
        )

        with pytest.raises(ModelLoadError):
            load_model(str(temp_model_dir))


class TestValidateModelInterface:
    """Tests for validate_model_interface function."""

    def test_validate_valid_model(self):
        """Test validation of valid model."""
        model = MockModel()

        # Should not raise
        validate_model_interface(model)

    def test_validate_missing_method(self):
        """Test validation fails for missing method."""
        model = IncompleteModel()

        with pytest.raises(ModelLoadError, match="must implement"):
            validate_model_interface(model)

    def test_validate_non_callable_method(self):
        """Test validation fails for non-callable attribute."""

        class BadModel:
            load = "not a method"

        model = BadModel()

        with pytest.raises(ModelLoadError, match="must be callable"):
            validate_model_interface(model)

    @pytest.mark.parametrize(
        "method_name",
        ["load", "warmup", "batch_size", "batch_wait_s", "encode"],
    )
    def test_validate_each_required_method(self, method_name):
        """Test each required method is validated."""

        class PartialModel:
            pass

        model = PartialModel()

        # Add all methods except the one being tested
        for method in ["load", "warmup", "batch_size", "batch_wait_s", "encode"]:
            if method != method_name:
                setattr(model, method, lambda: None)

        with pytest.raises(ModelLoadError, match=f"'{method_name}'"):
            validate_model_interface(model)
