import asyncio
import logging
from collections import defaultdict
from typing import AsyncGenerator

logger = logging.getLogger(__name__)


class RunEventBroadcaster:
    """In-memory pub/sub for streaming run execution events to SSE clients."""

    def __init__(self, queue_maxsize: int = 256):
        self._channels: dict[str, set[asyncio.Queue]] = defaultdict(set)
        self._queue_maxsize = queue_maxsize

    def publish(self, run_id: str, event_type: str, data: dict) -> None:
        queues = self._channels.get(run_id)
        if not queues:
            return
        event = {"type": event_type, "data": data}
        for q in queues:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(
                    "broadcast queue full run_id=%s, dropping event", run_id
                )

    def close(self, run_id: str) -> None:
        queues = self._channels.pop(run_id, None)
        if not queues:
            return
        for q in queues:
            try:
                q.put_nowait(None)  # sentinel signals end of stream
            except asyncio.QueueFull:
                pass

    async def subscribe(self, run_id: str) -> AsyncGenerator[dict, None]:
        q: asyncio.Queue = asyncio.Queue(maxsize=self._queue_maxsize)
        self._channels[run_id].add(q)
        try:
            while True:
                event = await q.get()
                if event is None:
                    break
                yield event
        finally:
            self._channels.get(run_id, set()).discard(q)
            if run_id in self._channels and not self._channels[run_id]:
                del self._channels[run_id]
