"""In-process fan-out for live audit rows.

The Fleet Activity panel and the Audit Log page subscribe over SSE. Rows are
pushed as they are written rather than polled, so a call made in Claude Desktop
shows up in the browser without a refresh.
"""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

# Bounded so a slow or abandoned browser tab can never grow without limit.
_QUEUE_MAX = 200
_RECENT_MAX = 50


class Hub:
    """Fan-out to every connected SSE listener."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[dict]] = set()
        self._recent: deque[dict] = deque(maxlen=_RECENT_MAX)
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Remember the app's loop so worker threads can publish into it."""
        self._loop = loop

    @contextmanager
    def subscribe(self) -> Iterator[asyncio.Queue[dict]]:
        queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=_QUEUE_MAX)
        self._subscribers.add(queue)
        try:
            yield queue
        finally:
            self._subscribers.discard(queue)

    def publish(self, payload: dict[str, Any]) -> None:
        """Publish a row. Safe to call from any thread."""
        self._recent.append(payload)
        if not self._subscribers:
            return
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None

        if running is not None:
            self._deliver(payload)
        elif self._loop is not None and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._deliver, payload)

    def _deliver(self, payload: dict[str, Any]) -> None:
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                # A listener that cannot keep up loses rows rather than
                # blocking the call it is observing.
                pass

    @property
    def recent(self) -> list[dict]:
        return list(self._recent)

    @property
    def listener_count(self) -> int:
        return len(self._subscribers)


hub = Hub()
