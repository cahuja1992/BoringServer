"""Pytest configuration and fixtures."""

import asyncio
import tempfile
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir():
    """Create a temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_config_data():
    """Provide mock configuration data."""
    return {
        "service": {
            "name": "test-service",
            "version": "1.0.0",
            "host": "0.0.0.0",
            "port": 8000,
        },
        "logging": {
            "level": "INFO",
        },
        "server": {
            "max_queue_size": 100,
        },
    }


@pytest.fixture
def mock_model_config():
    """Provide mock model configuration."""
    return {
        "name": "test-model",
        "version": "1.0.0",
        "description": "A test model",
        "batch_size": 8,
        "batch_wait_s": 0.001,
    }


@pytest.fixture
def mock_model_implementation():
    """Provide mock model implementation code."""
    return '''
class ModelImpl:
    def load(self):
        """Load model."""
        self.loaded = True
    
    def warmup(self):
        """Warmup model."""
        pass
    
    def batch_size(self):
        """Get batch size."""
        return 8
    
    def batch_wait_s(self):
        """Get batch wait time."""
        return 0.001
    
    def encode(self, batch):
        """Encode batch."""
        return [[0.1, 0.2, 0.3] for _ in batch]
'''
