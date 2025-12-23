"""Unit tests for request queue."""

import asyncio

import pytest

from engine.exceptions import QueueFullError
from engine.queue import RequestQueue
from engine.types import InferenceRequest


@pytest.fixture
def queue():
    """Create request queue fixture."""
    return RequestQueue(maxsize=10)


@pytest.fixture
def inference_request():
    """Create inference request fixture."""
    future = asyncio.Future()
    return InferenceRequest(payload={"test": "data"}, future=future)


class TestRequestQueue:
    """Tests for RequestQueue."""

    def test_initialization(self):
        """Test queue initialization."""
        queue = RequestQueue(maxsize=100)
        assert queue.maxsize == 100
        assert queue.depth() == 0
        assert queue.is_empty()
        assert not queue.is_full()

    @pytest.mark.asyncio
    async def test_put(self, queue, inference_request):
        """Test adding request to queue."""
        await queue.put(inference_request)
        assert queue.depth() == 1
        assert not queue.is_empty()

    @pytest.mark.asyncio
    async def test_put_queue_full(self, inference_request):
        """Test queue full error."""
        small_queue = RequestQueue(maxsize=1)

        # Fill queue
        await small_queue.put(inference_request)

        # Try to add another
        future = asyncio.Future()
        request2 = InferenceRequest(payload={"test": "data2"}, future=future)

        with pytest.raises(QueueFullError) as exc_info:
            await small_queue.put(request2)

        assert "full" in str(exc_info.value).lower()
        assert exc_info.value.queue_depth == 1

    @pytest.mark.asyncio
    async def test_get_batch_single(self, queue, inference_request):
        """Test getting single request as batch."""
        await queue.put(inference_request)

        batch = await queue.get_batch(batch_size=5, timeout_s=0.1)

        assert len(batch) == 1
        assert batch[0] == inference_request
        assert queue.is_empty()

    @pytest.mark.asyncio
    async def test_get_batch_multiple(self, queue):
        """Test getting multiple requests as batch."""
        # Add multiple requests
        requests = []
        for i in range(3):
            future = asyncio.Future()
            req = InferenceRequest(payload={"id": i}, future=future)
            await queue.put(req)
            requests.append(req)

        batch = await queue.get_batch(batch_size=5, timeout_s=0.1)

        assert len(batch) == 3
        assert batch == requests
        assert queue.is_empty()

    @pytest.mark.asyncio
    async def test_get_batch_limited_by_size(self, queue):
        """Test batch size limit."""
        # Add 5 requests
        for i in range(5):
            future = asyncio.Future()
            req = InferenceRequest(payload={"id": i}, future=future)
            await queue.put(req)

        # Get batch of max 3
        batch = await queue.get_batch(batch_size=3, timeout_s=0.1)

        assert len(batch) == 3
        assert queue.depth() == 2  # 2 remaining

    @pytest.mark.asyncio
    async def test_get_batch_timeout(self, queue):
        """Test batch get timeout."""
        # Empty queue should timeout
        batch = await queue.get_batch(batch_size=5, timeout_s=0.01)

        assert len(batch) == 0

    @pytest.mark.asyncio
    async def test_get_batch_waits_for_first(self, queue):
        """Test that get_batch waits for first request."""

        async def add_delayed():
            await asyncio.sleep(0.05)
            future = asyncio.Future()
            req = InferenceRequest(payload={"delayed": True}, future=future)
            await queue.put(req)

        # Start adding request in background
        task = asyncio.create_task(add_delayed())

        # This should wait and get the request
        batch = await queue.get_batch(batch_size=5, timeout_s=0.2)

        await task

        assert len(batch) == 1
        assert batch[0].payload["delayed"] is True

    def test_depth(self, queue):
        """Test queue depth."""
        assert queue.depth() == 0

        future = asyncio.Future()
        req = InferenceRequest(payload={}, future=future)

        asyncio.run(queue.put(req))
        assert queue.depth() == 1

    def test_is_empty(self, queue):
        """Test is_empty check."""
        assert queue.is_empty()

        future = asyncio.Future()
        req = InferenceRequest(payload={}, future=future)
        asyncio.run(queue.put(req))

        assert not queue.is_empty()

    def test_is_full(self):
        """Test is_full check."""
        small_queue = RequestQueue(maxsize=1)
        assert not small_queue.is_full()

        future = asyncio.Future()
        req = InferenceRequest(payload={}, future=future)
        asyncio.run(small_queue.put(req))

        assert small_queue.is_full()

    def test_get_metrics(self, queue):
        """Test getting queue metrics."""
        metrics = queue.get_metrics()

        assert "depth" in metrics
        assert "maxsize" in metrics
        assert "total_requests" in metrics
        assert "total_rejections" in metrics
        assert "total_timeouts" in metrics
        assert "utilization" in metrics

        assert metrics["depth"] == 0
        assert metrics["maxsize"] == 10
        assert metrics["total_requests"] == 0
        assert metrics["utilization"] == 0.0

    @pytest.mark.asyncio
    async def test_metrics_tracking(self, queue):
        """Test that metrics are tracked correctly."""
        # Add requests
        for i in range(3):
            future = asyncio.Future()
            req = InferenceRequest(payload={"id": i}, future=future)
            await queue.put(req)

        metrics = queue.get_metrics()
        assert metrics["total_requests"] == 3
        assert metrics["depth"] == 3
        assert metrics["utilization"] == 0.3

        # Get batch
        await queue.get_batch(batch_size=5, timeout_s=0.1)

        metrics = queue.get_metrics()
        assert metrics["depth"] == 0
        assert metrics["utilization"] == 0.0

    @pytest.mark.asyncio
    async def test_rejection_tracking(self):
        """Test rejection tracking."""
        small_queue = RequestQueue(maxsize=1)

        future1 = asyncio.Future()
        req1 = InferenceRequest(payload={}, future=future1)
        await small_queue.put(req1)

        # Try to add when full
        future2 = asyncio.Future()
        req2 = InferenceRequest(payload={}, future=future2)

        with pytest.raises(QueueFullError):
            await small_queue.put(req2)

        metrics = small_queue.get_metrics()
        assert metrics["total_rejections"] == 1

    @pytest.mark.asyncio
    async def test_timeout_tracking(self, queue):
        """Test timeout tracking."""
        # Empty queue should timeout
        await queue.get_batch(batch_size=5, timeout_s=0.01)

        metrics = queue.get_metrics()
        assert metrics["total_timeouts"] == 1
