"""
Live event hub — in-process pub/sub for call transcripts.

The Vapi webhook receives transcript events and publishes them here, keyed by
call_id. SSE endpoints subscribe per call_id and stream events to the browser.

This is in-process: it works because the webhook handler and the SSE endpoint
run in the same FastAPI process. For a multi-instance production deployment
this would be swapped for Redis pub/sub (an event arriving on instance A must
reach a browser connected to instance B) — but for the demo, in-process is
correct and simple.
"""

import asyncio
from collections import defaultdict

# Per-subscriber queue cap. A paused or slow consumer (e.g. a backgrounded
# browser tab) cannot then grow memory without bound on a long call. On
# overflow we drop the oldest event — for a live transcript the newest lines
# are what the viewer wants to see.
MAX_QUEUE_SIZE = 1000


class EventHub:
    """Per-call fan-out of events to any number of subscribers."""

    def __init__(self) -> None:
        # call_id -> set of subscriber queues
        self._subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)

    def subscribe(self, call_id: str) -> asyncio.Queue:
        """Register a subscriber for a call. Returns a queue to read from."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=MAX_QUEUE_SIZE)
        self._subscribers[call_id].add(queue)
        return queue

    def unsubscribe(self, call_id: str, queue: asyncio.Queue) -> None:
        """Remove a subscriber. Safe to call more than once."""
        subs = self._subscribers.get(call_id)
        if subs is not None:
            subs.discard(queue)
            if not subs:
                del self._subscribers[call_id]

    async def publish(self, call_id: str, event: dict) -> None:
        """Send an event to every subscriber of a call.

        If there are no subscribers (no dashboard watching), the event is
        simply dropped — that is fine, it is a live feed, not a log.

        A single stuck subscriber must not block delivery to the others, so
        we use put_nowait and drop the oldest event on overflow.
        """
        for queue in list(self._subscribers.get(call_id, ())):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    pass

    def subscriber_count(self, call_id: str) -> int:
        """How many dashboards are watching a call — useful for tests/debug."""
        return len(self._subscribers.get(call_id, ()))


# single shared instance for the app's lifetime
hub = EventHub()
