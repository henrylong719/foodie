"""Unit test: event hub pub/sub and the transcript webhook path.

Tests the relay logic directly (no HTTP). The end-to-end SSE streaming test
is separate (test_sse_e2e.py) since it needs a real running server.
"""

import asyncio

from app.services.event_hub import EventHub
import app.routers.calls as calls


class _FakeRequest:
    def __init__(self, body):
        self._body = body

    async def json(self):
        return self._body


async def run():
    # --- hub: subscribe / publish / receive ---
    h = EventHub()
    q = h.subscribe("call-1")
    assert h.subscriber_count("call-1") == 1
    await h.publish("call-1", {"text": "hello"})
    got = await asyncio.wait_for(q.get(), timeout=1)
    assert got == {"text": "hello"}
    print("  hub publish/receive  -> ok")

    # --- hub: fan-out to multiple subscribers ---
    q2 = h.subscribe("call-1")
    await h.publish("call-1", {"text": "broadcast"})
    a = await asyncio.wait_for(q.get(), timeout=1)
    b = await asyncio.wait_for(q2.get(), timeout=1)
    assert a == b == {"text": "broadcast"}
    print("  hub fan-out (2 subs) -> ok")

    # --- hub: publish with no subscribers is a safe no-op ---
    await h.publish("call-nobody", {"text": "dropped"})
    print("  hub no-subscriber    -> dropped safely")

    # --- hub: unsubscribe cleans up ---
    h.unsubscribe("call-1", q)
    h.unsubscribe("call-1", q2)
    assert h.subscriber_count("call-1") == 0
    h.unsubscribe("call-1", q)  # double unsubscribe must not error
    print("  hub unsubscribe      -> cleaned up")

    # --- webhook: a transcript message publishes to the shared hub ---
    listener = calls.hub.subscribe("call-X")
    body = {
        "message": {
            "type": "transcript",
            "transcriptType": "final",
            "role": "user",
            "transcript": "I need some chips",
            "call": {"id": "call-X"},
        }
    }
    resp = await calls.vapi_webhook(_FakeRequest(body), db=None)
    assert resp == {"received": True}
    line = await asyncio.wait_for(listener.get(), timeout=1)
    assert line["role"] == "customer", "Vapi 'user' must map to 'customer'"
    assert line["text"] == "I need some chips"
    print(f"  transcript webhook   -> published as {line['role']}")

    # --- webhook: assistant role passes through ---
    body = {
        "message": {
            "type": "transcript",
            "transcriptType": "final",
            "role": "assistant",
            "transcript": "Sure, how many?",
            "call": {"id": "call-X"},
        }
    }
    await calls.vapi_webhook(_FakeRequest(body), db=None)
    line = await asyncio.wait_for(listener.get(), timeout=1)
    assert line["role"] == "assistant"
    print("  assistant transcript -> role preserved")

    # --- webhook: PARTIAL transcripts are NOT forwarded (would flicker UI) ---
    body = {
        "message": {
            "type": "transcript",
            "transcriptType": "partial",
            "role": "user",
            "transcript": "I need some ch...",
            "call": {"id": "call-X"},
        }
    }
    await calls.vapi_webhook(_FakeRequest(body), db=None)
    await asyncio.sleep(0.05)
    assert listener.empty(), "partial transcripts must not be published"
    print("  partial transcript   -> correctly dropped")

    # --- webhook: transcriptType omitted defaults to final (Vapi behaviour) ---
    body = {
        "message": {
            "type": "transcript",
            "role": "user",
            "transcript": "no type field",
            "call": {"id": "call-X"},
        }
    }
    await calls.vapi_webhook(_FakeRequest(body), db=None)
    line = await asyncio.wait_for(listener.get(), timeout=1)
    assert line["text"] == "no type field"
    print("  omitted type         -> treated as final")

    calls.hub.unsubscribe("call-X", listener)


asyncio.run(run())
print("\nALL EVENT HUB / RELAY CHECKS PASSED")
