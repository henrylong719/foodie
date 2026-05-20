"""Unit test: event hub pub/sub and the transcript webhook path.

Tests the relay logic directly (no HTTP). The end-to-end SSE streaming test
is separate (test_sse_e2e.py) since it needs a real running server.
"""

import asyncio

from app.services.event_hub import MAX_QUEUE_SIZE, EventHub
import app.routers.calls as calls


class _FakeRequest:
    def __init__(self, body):
        self._body = body

    async def json(self):
        return self._body


class _FakeCalls:
    async def update_one(self, *args, **kwargs):
        return None


class _FakeUpdateResult:
    matched_count = 1


class _FakeCustomers:
    async def update_one(self, *args, **kwargs):
        return _FakeUpdateResult()


class _FakeDb:
    calls = _FakeCalls()
    customers = _FakeCustomers()


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

    # --- hub: bounded queue caps memory for a stuck subscriber ---
    # If a subscriber never drains (paused tab) and the publisher keeps
    # going, the queue must not grow without bound — oldest events get
    # dropped so newest survive and publish never blocks.
    h_slow = EventHub()
    q_slow = h_slow.subscribe("call-slow")
    overflow_by = 50
    total = MAX_QUEUE_SIZE + overflow_by
    for i in range(total):
        await h_slow.publish("call-slow", {"i": i})
    assert q_slow.qsize() == MAX_QUEUE_SIZE, (
        f"expected cap at {MAX_QUEUE_SIZE}, got {q_slow.qsize()}"
    )
    first = q_slow.get_nowait()
    assert first["i"] == overflow_by, (
        f"oldest {overflow_by} events should have been dropped, got first={first['i']}"
    )
    last = first
    while not q_slow.empty():
        last = q_slow.get_nowait()
    assert last["i"] == total - 1, "newest event should be retained"
    h_slow.unsubscribe("call-slow", q_slow)
    print(f"  bounded queue cap    -> capped at {MAX_QUEUE_SIZE}, drop-oldest")

    # --- hub: a stuck subscriber must not starve a healthy one ---
    h_fan = EventHub()
    stuck = h_fan.subscribe("call-fan")
    healthy = h_fan.subscribe("call-fan")
    for i in range(MAX_QUEUE_SIZE + 5):
        await h_fan.publish("call-fan", {"i": i})
    # healthy subscriber receives the latest event despite stuck peer
    assert healthy.qsize() == MAX_QUEUE_SIZE
    drained = []
    while not healthy.empty():
        drained.append(healthy.get_nowait()["i"])
    assert drained[-1] == MAX_QUEUE_SIZE + 4
    h_fan.unsubscribe("call-fan", stuck)
    h_fan.unsubscribe("call-fan", healthy)
    print("  stuck peer isolation -> healthy subscriber unaffected")

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
    db = _FakeDb()
    resp = await calls.vapi_webhook(_FakeRequest(body), db=db)
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
    await calls.vapi_webhook(_FakeRequest(body), db=db)
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
    await calls.vapi_webhook(_FakeRequest(body), db=db)
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
    await calls.vapi_webhook(_FakeRequest(body), db=db)
    line = await asyncio.wait_for(listener.get(), timeout=1)
    assert line["text"] == "no type field"
    print("  omitted type         -> treated as final")

    calls.hub.unsubscribe("call-X", listener)

    # --- webhook: DNC tool success publishes a live transcript annotation ---
    dnc_listener = calls.hub.subscribe("call-DNC")
    body = {
        "message": {
            "type": "tool-calls",
            "toolCallList": [
                {"id": "tcD", "name": "flag_do_not_call", "arguments": {}}
            ],
            "call": {
                "id": "call-DNC",
                "metadata": {"customer_id": "507f1f77bcf86cd799439011"},
            },
        }
    }
    resp = await calls.vapi_webhook(_FakeRequest(body), db=db)
    assert resp["results"][0]["result"]["ok"] is True
    line = await asyncio.wait_for(dnc_listener.get(), timeout=1)
    assert line["role"] == "assistant"
    assert line["text"] == "DNC flagged"
    assert line["type"] == "annotation"
    calls.hub.unsubscribe("call-DNC", dnc_listener)
    print("  DNC tool annotation  -> published live")


asyncio.run(run())
print("\nALL EVENT HUB / RELAY CHECKS PASSED")
