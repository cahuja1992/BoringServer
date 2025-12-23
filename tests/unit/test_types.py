"""Unit tests for types module."""

import asyncio
import time

import pytest

from engine.types import InferenceRequest, InferenceResponse, ModelInfo


class TestInferenceRequest:
    """Tests for InferenceRequest."""

    def test_creation_with_defaults(self):
        """Test creating request with default values."""
        future = asyncio.Future()
        payload = {"image": "test", "text": "test"}

        request = InferenceRequest(payload=payload, future=future)

        assert request.payload == payload
        assert request.future == future
        assert request.request_id is not None
        assert len(request.request_id) > 0
        assert request.enqueue_ts > 0
        assert isinstance(request.metadata, dict)
        assert len(request.metadata) == 0

    def test_unique_request_ids(self):
        """Test that each request gets a unique ID."""
        future1 = asyncio.Future()
        future2 = asyncio.Future()

        request1 = InferenceRequest(payload={}, future=future1)
        request2 = InferenceRequest(payload={}, future=future2)

        assert request1.request_id != request2.request_id

    def test_age_ms(self):
        """Test calculating request age in milliseconds."""
        future = asyncio.Future()
        request = InferenceRequest(payload={}, future=future)

        time.sleep(0.01)  # Wait 10ms

        age = request.age_ms()
        assert age >= 10
        assert age < 100  # Should be less than 100ms

    def test_age_ms_increases(self):
        """Test that age increases over time."""
        future = asyncio.Future()
        request = InferenceRequest(payload={}, future=future)

        age1 = request.age_ms()
        time.sleep(0.01)
        age2 = request.age_ms()

        assert age2 > age1

    def test_to_dict(self):
        """Test converting request to dictionary."""
        future = asyncio.Future()
        payload = {"test": "data"}
        metadata = {"key": "value"}

        request = InferenceRequest(
            payload=payload,
            future=future,
            metadata=metadata,
        )

        result = request.to_dict()

        assert "request_id" in result
        assert "enqueue_ts" in result
        assert "age_ms" in result
        assert "metadata" in result
        assert result["request_id"] == request.request_id
        assert result["metadata"] == metadata

    def test_custom_metadata(self):
        """Test request with custom metadata."""
        future = asyncio.Future()
        metadata = {"user_id": "123", "priority": "high"}

        request = InferenceRequest(
            payload={},
            future=future,
            metadata=metadata,
        )

        assert request.metadata == metadata


class TestInferenceResponse:
    """Tests for InferenceResponse."""

    def test_creation(self):
        """Test creating response."""
        output = [0.1, 0.2, 0.3]
        request_id = "test-id"
        processing_time = 50.5

        response = InferenceResponse(
            output=output,
            request_id=request_id,
            processing_time_ms=processing_time,
        )

        assert response.output == output
        assert response.request_id == request_id
        assert response.processing_time_ms == processing_time
        assert response.batch_size == 1
        assert isinstance(response.metadata, dict)

    def test_creation_with_batch_size(self):
        """Test creating response with batch size."""
        response = InferenceResponse(
            output=[0.1, 0.2],
            request_id="test",
            processing_time_ms=10.0,
            batch_size=8,
        )

        assert response.batch_size == 8

    def test_creation_with_metadata(self):
        """Test creating response with metadata."""
        metadata = {"model": "test-model", "version": "1.0"}

        response = InferenceResponse(
            output=[],
            request_id="test",
            processing_time_ms=10.0,
            metadata=metadata,
        )

        assert response.metadata == metadata

    def test_to_dict(self):
        """Test converting response to dictionary."""
        output = [0.1, 0.2, 0.3]
        request_id = "test-123"
        processing_time = 25.5
        batch_size = 4
        metadata = {"key": "value"}

        response = InferenceResponse(
            output=output,
            request_id=request_id,
            processing_time_ms=processing_time,
            batch_size=batch_size,
            metadata=metadata,
        )

        result = response.to_dict()

        assert result["output"] == output
        assert result["request_id"] == request_id
        assert result["processing_time_ms"] == processing_time
        assert result["batch_size"] == batch_size
        assert result["metadata"] == metadata


class TestModelInfo:
    """Tests for ModelInfo."""

    def test_creation_minimal(self):
        """Test creating ModelInfo with minimal fields."""
        info = ModelInfo(name="test-model")

        assert info.name == "test-model"
        assert info.version is None
        assert info.description is None
        assert info.batch_size == 16
        assert info.batch_wait_s == 0.003
        assert isinstance(info.metadata, dict)

    def test_creation_full(self):
        """Test creating ModelInfo with all fields."""
        metadata = {"framework": "pytorch"}

        info = ModelInfo(
            name="test-model",
            version="1.0.0",
            description="Test model description",
            batch_size=32,
            batch_wait_s=0.01,
            metadata=metadata,
        )

        assert info.name == "test-model"
        assert info.version == "1.0.0"
        assert info.description == "Test model description"
        assert info.batch_size == 32
        assert info.batch_wait_s == 0.01
        assert info.metadata == metadata

    def test_to_dict(self):
        """Test converting ModelInfo to dictionary."""
        info = ModelInfo(
            name="test-model",
            version="2.0",
            description="A test model",
            batch_size=8,
            batch_wait_s=0.005,
            metadata={"type": "embedding"},
        )

        result = info.to_dict()

        assert result["name"] == "test-model"
        assert result["version"] == "2.0"
        assert result["description"] == "A test model"
        assert result["batch_size"] == 8
        assert result["batch_wait_s"] == 0.005
        assert result["metadata"] == {"type": "embedding"}

    def test_default_values(self):
        """Test default values are used."""
        info = ModelInfo(name="minimal")

        result = info.to_dict()

        assert result["batch_size"] == 16
        assert result["batch_wait_s"] == 0.003
        assert result["metadata"] == {}
