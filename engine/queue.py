"""Enhanced request queue with monitoring."""

import asyncio
import time
from typing import List, Optional

from engine.exceptions import QueueFullError
from engine.logging import get_logger
from engine.types import InferenceRequest

logger = get_logger(__name__)


class RequestQueue:
    """Request queue with monitoring and metrics."""

    def __init__(self, maxsize: int = 1024):
        """Initialize request queue.

        Args:
            maxsize: Maximum queue size
        """
        self.q = asyncio.Queue(maxsize=maxsize)
        self.maxsize = maxsize
        self._total_requests = 0
        self._total_rejections = 0
        self._total_timeouts = 0

    async def put(self, req: InferenceRequest) -> None:
        """Add request to queue.

        Args:
            req: Inference request

        Raises:
            QueueFullError: If queue is full
        """
        try:
            self.q.put_nowait(req)
            self._total_requests += 1
            logger.debug(
                f"Request enqueued: {req.request_id}, queue_depth={self.depth()}",
                extra={"request_id": req.request_id},
            )
        except asyncio.QueueFull:
            self._total_rejections += 1
            logger.warning(
                f"Queue full, rejecting request: {req.request_id}",
                extra={"request_id": req.request_id, "queue_depth": self.depth()},
            )
            raise QueueFullError("Request queue is full", queue_depth=self.depth())

    async def get_batch(
        self, batch_size: int, timeout_s: float
    ) -> List[InferenceRequest]:
        """Get batch of requests from queue.

        Args:
            batch_size: Maximum batch size
            timeout_s: Timeout in seconds

        Returns:
            List of inference requests
        """
        batch: List[InferenceRequest] = []
        start_time = time.time()

        try:
            # Wait for first request
            first_req = await asyncio.wait_for(self.q.get(), timeout_s)
            batch.append(first_req)
        except asyncio.TimeoutError:
            self._total_timeouts += 1
            return []

        # Try to get more requests to fill the batch
        while len(batch) < batch_size:
            try:
                req = self.q.get_nowait()
                batch.append(req)
            except asyncio.QueueEmpty:
                break

        elapsed = (time.time() - start_time) * 1000
        logger.debug(
            f"Batch created: size={len(batch)}, wait_time_ms={elapsed:.2f}",
            extra={"batch_size": len(batch), "duration_ms": elapsed},
        )

        return batch

    def depth(self) -> int:
        """Get current queue depth.

        Returns:
            Number of items in queue
        """
        return self.q.qsize()

    def is_empty(self) -> bool:
        """Check if queue is empty.

        Returns:
            True if empty
        """
        return self.q.empty()

    def is_full(self) -> bool:
        """Check if queue is full.

        Returns:
            True if full
        """
        return self.q.full()

    def get_metrics(self) -> dict:
        """Get queue metrics.

        Returns:
            Dictionary of metrics
        """
        return {
            "depth": self.depth(),
            "maxsize": self.maxsize,
            "total_requests": self._total_requests,
            "total_rejections": self._total_rejections,
            "total_timeouts": self._total_timeouts,
            "utilization": self.depth() / self.maxsize if self.maxsize > 0 else 0,
        }
