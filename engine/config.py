"""Configuration management for inference engine."""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServiceConfig(BaseSettings):
    """Service-level configuration."""

    name: str = "inference-engine"
    version: str = "1.0.0"
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1


class RayConfig(BaseSettings):
    """Ray configuration."""

    num_gpus: int = 1
    include_dashboard: bool = False
    log_to_driver: bool = True


class ServerConfig(BaseSettings):
    """Server configuration."""

    max_queue_size: int = 1024
    request_timeout_s: int = 30
    shutdown_timeout_s: int = 60


class LoggingConfig(BaseSettings):
    """Logging configuration."""

    level: str = "INFO"
    format: str = "json"
    output: str = "stdout"

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        """Validate logging level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v = v.upper()
        if v not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v


class MetricsConfig(BaseSettings):
    """Metrics configuration."""

    enabled: bool = True
    port: int = 9090
    path: str = "/metrics"


class HealthConfig(BaseSettings):
    """Health check configuration."""

    enabled: bool = True
    path: str = "/health"
    readiness_path: str = "/ready"


class ModelsConfig(BaseSettings):
    """Models configuration."""

    default_batch_size: int = 16
    default_batch_wait_s: float = 0.003
    warmup_enabled: bool = True


class SecurityConfig(BaseSettings):
    """Security configuration."""

    rate_limit_enabled: bool = True
    rate_limit_requests: int = 100
    rate_limit_period_s: int = 60
    max_upload_size_mb: int = 10


class Config(BaseSettings):
    """Main configuration class."""

    model_config = SettingsConfigDict(
        env_prefix="INFERENCE_",
        env_nested_delimiter="__",
        case_sensitive=False,
    )

    service: ServiceConfig = Field(default_factory=ServiceConfig)
    ray: RayConfig = Field(default_factory=RayConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    metrics: MetricsConfig = Field(default_factory=MetricsConfig)
    health: HealthConfig = Field(default_factory=HealthConfig)
    models: ModelsConfig = Field(default_factory=ModelsConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)

    @classmethod
    def from_yaml(cls, config_path: str) -> "Config":
        """Load configuration from YAML file.

        Args:
            config_path: Path to configuration file

        Returns:
            Config instance

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config file is invalid
        """
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(path) as f:
            data = yaml.safe_load(f)

        # Handle 'extends' directive
        if "extends" in data:
            base_path = path.parent / data.pop("extends")
            if base_path.exists():
                with open(base_path) as f:
                    base_data = yaml.safe_load(f)
                data = cls._merge_configs(base_data, data)

        return cls(**data)

    @staticmethod
    def _merge_configs(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively merge configuration dictionaries.

        Args:
            base: Base configuration
            override: Override configuration

        Returns:
            Merged configuration
        """
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = Config._merge_configs(result[key], value)
            else:
                result[key] = value
        return result


def load_config(config_path: Optional[str] = None, env: Optional[str] = None) -> Config:
    """Load configuration from file or environment.

    Args:
        config_path: Path to configuration file
        env: Environment name (dev, prod, etc.)

    Returns:
        Config instance
    """
    if config_path:
        return Config.from_yaml(config_path)

    # Try to load from environment variable
    config_path = os.getenv("INFERENCE_CONFIG_PATH")
    if config_path:
        return Config.from_yaml(config_path)

    # Try to load from standard locations
    if env:
        config_dir = Path(__file__).parent.parent / "configs"
        config_file = config_dir / f"{env}.yaml"
        if config_file.exists():
            return Config.from_yaml(str(config_file))

    # Return default configuration
    return Config()


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get global configuration instance."""
    global _config
    if _config is None:
        env = os.getenv("ENVIRONMENT", "dev")
        _config = load_config(env=env)
    return _config


def set_config(config: Config) -> None:
    """Set global configuration instance."""
    global _config
    _config = config
