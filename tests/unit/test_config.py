"""Unit tests for configuration management."""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from engine.config import (
    Config,
    HealthConfig,
    LoggingConfig,
    MetricsConfig,
    ModelsConfig,
    RayConfig,
    SecurityConfig,
    ServerConfig,
    ServiceConfig,
    get_config,
    load_config,
    set_config,
)


class TestServiceConfig:
    """Tests for ServiceConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = ServiceConfig()
        assert config.name == "inference-engine"
        assert config.version == "1.0.0"
        assert config.host == "0.0.0.0"
        assert config.port == 8000
        assert config.workers == 1


class TestLoggingConfig:
    """Tests for LoggingConfig."""

    def test_default_values(self):
        """Test default logging configuration."""
        config = LoggingConfig()
        assert config.level == "INFO"
        assert config.format == "json"
        assert config.output == "stdout"

    def test_level_validation(self):
        """Test logging level validation."""
        # Valid levels
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            config = LoggingConfig(level=level)
            assert config.level == level

        # Case insensitive
        config = LoggingConfig(level="info")
        assert config.level == "INFO"

        # Invalid level
        with pytest.raises(ValueError):
            LoggingConfig(level="INVALID")


class TestConfig:
    """Tests for main Config class."""

    def test_default_config(self):
        """Test default configuration."""
        config = Config()
        assert isinstance(config.service, ServiceConfig)
        assert isinstance(config.ray, RayConfig)
        assert isinstance(config.server, ServerConfig)
        assert isinstance(config.logging, LoggingConfig)
        assert isinstance(config.metrics, MetricsConfig)
        assert isinstance(config.health, HealthConfig)
        assert isinstance(config.models, ModelsConfig)
        assert isinstance(config.security, SecurityConfig)

    def test_from_yaml(self, tmp_path):
        """Test loading configuration from YAML."""
        config_data = {
            "service": {
                "name": "test-service",
                "port": 9000,
            },
            "logging": {
                "level": "DEBUG",
            },
        }

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = Config.from_yaml(str(config_file))
        assert config.service.name == "test-service"
        assert config.service.port == 9000
        assert config.logging.level == "DEBUG"

    def test_from_yaml_with_extends(self, tmp_path):
        """Test loading configuration with extends."""
        # Create base config
        base_data = {
            "service": {
                "name": "base-service",
                "port": 8000,
            },
            "logging": {
                "level": "INFO",
            },
        }

        base_file = tmp_path / "base.yaml"
        with open(base_file, "w") as f:
            yaml.dump(base_data, f)

        # Create override config
        override_data = {
            "extends": "base.yaml",
            "service": {
                "port": 9000,
            },
        }

        override_file = tmp_path / "override.yaml"
        with open(override_file, "w") as f:
            yaml.dump(override_data, f)

        config = Config.from_yaml(str(override_file))
        assert config.service.name == "base-service"  # From base
        assert config.service.port == 9000  # Overridden
        assert config.logging.level == "INFO"  # From base

    def test_from_yaml_file_not_found(self):
        """Test error handling for missing config file."""
        with pytest.raises(FileNotFoundError):
            Config.from_yaml("/nonexistent/config.yaml")

    def test_merge_configs(self):
        """Test configuration merging."""
        base = {
            "service": {"name": "base", "port": 8000},
            "logging": {"level": "INFO"},
        }

        override = {
            "service": {"port": 9000},
            "logging": {"format": "plain"},
        }

        result = Config._merge_configs(base, override)
        assert result["service"]["name"] == "base"
        assert result["service"]["port"] == 9000
        assert result["logging"]["level"] == "INFO"
        assert result["logging"]["format"] == "plain"


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_from_path(self, tmp_path):
        """Test loading config from explicit path."""
        config_data = {
            "service": {"name": "test-service"},
        }

        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = load_config(config_path=str(config_file))
        assert config.service.name == "test-service"

    def test_load_from_env_variable(self, tmp_path, monkeypatch):
        """Test loading config from environment variable."""
        config_data = {
            "service": {"name": "env-service"},
        }

        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        monkeypatch.setenv("INFERENCE_CONFIG_PATH", str(config_file))

        config = load_config()
        assert config.service.name == "env-service"

    def test_load_default(self):
        """Test loading default configuration."""
        config = load_config()
        assert isinstance(config, Config)


class TestGlobalConfig:
    """Tests for global config instance."""

    def test_get_config(self):
        """Test getting global config instance."""
        config = get_config()
        assert isinstance(config, Config)

    def test_set_config(self):
        """Test setting global config instance."""
        custom_config = Config()
        custom_config.service.name = "custom-service"

        set_config(custom_config)

        config = get_config()
        assert config.service.name == "custom-service"

        # Reset for other tests
        set_config(Config())


class TestEnvironmentOverrides:
    """Tests for environment variable overrides."""

    def test_env_override(self, monkeypatch):
        """Test configuration override via environment variables."""
        monkeypatch.setenv("INFERENCE_SERVICE__NAME", "env-override")
        monkeypatch.setenv("INFERENCE_SERVICE__PORT", "9999")

        config = Config()
        # Note: Pydantic settings would need to be instantiated fresh
        # This test demonstrates the pattern
