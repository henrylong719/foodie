"""Test the Vapi webhook: payload dispatch, results shape, all four tools.

Drives the webhook handler directly with realistic Vapi 'tool-calls' payloads.
mongomock + async adapter (sync-only, no $text).
"""
import asyncio
from datetime import datetime, timedelta, timezone

import mongomock
from bson import ObjectId

import app.routers.calls as calls
from app.services import vapi_client


# --- async adapter ----------------------------------------------------------
class _Cur:
    def __init__(self, c): self._c = c
    def sort(self, *a, **k): return _Cur(self._c.sort(*a, **k))
    async def to_list(self, length=None):
        d = list(self._c)
        return d[:length] if length is not None else d


class _Coll:
    def __init__(self, c): self._c = c
    def find(self, *a, **k): return _Cur(self._c.find(*a, **k))
    async def find_one(self, *a, **k): return self._c.find_one(*a, **k)
    async def distinct(self, *a, **k): return self._c.distinct(*a, **k)
    async def insert_one(self, *a, **k): return self._c.insert_one(*a, **k)
    async def update_one(self, *a, **k): return self._c.update_one(*a, **k)
    async def count_documents(self, *a, **k): return self._c.count_documents(*a, **k)


class _DB:
    def __init__(self, db): self._db = db
    def __getattr__(self, name): return _Coll(getattr(self._db, name))


# --- seed -------------------------------------------------------------------
_raw = mongomock.MongoClient()["test"]
CUST = ObjectId()
_raw.customers.insert_one({
    "_id": CUST, "name": "Test Customer", "phone": "+61400000000",
    "do_not_call": False, "consent": {"given": True}, "preferred_language": "en"})

chips_id = ObjectId()
_raw.products.insert_many([
    {"_id": chips_id, "name": "Smith's Original Potato Chips 150g",
     "brand": "Smith's", "category": "Snacks", "subcategory": "Chips",
     "aliases": ["chips"], "size": "150g", "unit": "packet",
     "price": 4.5, "in_stock": True, "popularity_score": 90},
    {"_id": ObjectId(), "name": "Doritos Cheese Corn Chips 170g",
     "brand": "Doritos", "category": "Snacks", "subcategory": "Chips",
     "aliases": ["chips"], "size": "170g", "unit": "packet",
     "price": 5.0, "in_stock": True, "popularity_score": 70},
])
_raw.brand_popularity.insert_one({
    "category": "Snacks", "subcategory": "Chips",
    "brand": "Doritos", "score": 100, "buyer_count": 8})
_raw.order_history.insert_one({
    "customer_id": CUST, "date": datetime.now(timezone.utc) - timedelta(days=10),
    "items": [{"product_id": chips_id, "name": "Smith's Original Potato Chips 150g",
               "category": "Snacks", "subcategory": "Chips", "quantity": 1}]})

db = _DB(_raw)


# --- a minimal fake Request that returns a fixed JSON body ------------------
class _FakeRequest:
    def __init__(self, body): self._body = body
    async def json(self): return self._body


def _payload(tool_calls, customer_id=str(CUST), call_id="call-123"):
    """Build a Vapi 'tool-calls' webhook payload."""
    return {"message": {
        "type": "tool-calls",
        "toolCallList": tool_calls,
        "call": {"id": call_id, "metadata": {"customer_id": customer_id}},
    }}


async def run():
    # --- 0. outbound call payload requests live server events from Vapi ---
    payload = vapi_client._build_call_payload(str(CUST), "+61400000000")
    server_messages = payload["assistantOverrides"]["serverMessages"]
    assert "tool-calls" in server_messages
    assert "transcript" in server_messages
    assert "status-update" in server_messages
    assert "end-of-call-report" in server_messages
    print("  call payload    -> requests live server messages")

    # --- 1. resolve_item via the webhook ---
    body = _payload([{"id": "tc1", "name": "resolve_item",
                      "arguments": {"mention": "chips"}}])
    resp = await calls.vapi_webhook(_FakeRequest(body), db)
    assert "results" in resp and len(resp["results"]) == 1
    assert resp["results"][0]["toolCallId"] == "tc1", "toolCallId must echo back"
    # customer has Smith's history -> confirm
    assert resp["results"][0]["result"]["status"] == "confirm"
    print(f"  resolve_item   -> {resp['results'][0]['result']['status']}")

    # --- 2. multiple tool calls in one request ---
    body = _payload([
        {"id": "tcA", "name": "resolve_item", "arguments": {"mention": "Doritos chips"}},
        {"id": "tcB", "name": "resolve_brand",
         "arguments": {"subcategory": "Chips", "brand": "Smith's"}},
    ])
    resp = await calls.vapi_webhook(_FakeRequest(body), db)
    assert len(resp["results"]) == 2, "both tool calls must be answered"
    ids = {r["toolCallId"] for r in resp["results"]}
    assert ids == {"tcA", "tcB"}
    print(f"  batch of 2     -> {len(resp['results'])} results, ids match")

    # --- 2b. Vapi docs currently show "parameters" as an args alias ---
    body = _payload([{"id": "tcP", "name": "resolve_item",
                      "parameters": {"mention": "chips"}}])
    resp = await calls.vapi_webhook(_FakeRequest(body), db)
    assert resp["results"][0]["result"]["status"] == "confirm"
    print("  parameters     -> accepted as arguments")

    # --- 2c. Some Vapi/Web SDK payloads use OpenAI-style nested function calls ---
    body = _payload([{"id": "tcF", "function": {
        "name": "resolve_item",
        "arguments": '{"mention": "chips"}',
    }}])
    resp = await calls.vapi_webhook(_FakeRequest(body), db)
    assert resp["results"][0]["result"]["status"] == "confirm"
    print("  function args  -> nested shape accepted")

    # --- 2d. Vapi may put name/parameters in toolWithToolCallList metadata ---
    body = _payload([{"id": "tcW"}])
    body["message"]["toolWithToolCallList"] = [{
        "name": "resolve_item",
        "toolCall": {"id": "tcW", "parameters": {"mention": "chips"}},
    }]
    resp = await calls.vapi_webhook(_FakeRequest(body), db)
    assert resp["results"][0]["result"]["status"] == "confirm"
    print("  tool metadata  -> fallback name/params accepted")

    # --- 3. save_order ---
    body = _payload([{"id": "tcS", "name": "save_order", "arguments": {
        "items": [{"product_id": str(chips_id),
                   "name": "Smith's Original Potato Chips 150g",
                   "quantity": 2, "brand_source": "history"}]}}])
    resp = await calls.vapi_webhook(_FakeRequest(body), db)
    res = resp["results"][0]["result"]
    assert res["ok"] is True and "order_id" in res
    saved = _raw.captured_orders.find_one({"_id": ObjectId(res["order_id"])})
    assert saved["items"][0]["quantity"] == 2
    assert saved["status"] == "pending_fulfilment"
    assert saved["call_id"] == "call-123", "call_id must come from call metadata"
    print(f"  save_order     -> saved order {res['order_id'][:8]}...")

    # --- 4. flag_do_not_call ---
    body = _payload([{"id": "tcD", "name": "flag_do_not_call", "arguments": {}}])
    resp = await calls.vapi_webhook(_FakeRequest(body), db)
    assert resp["results"][0]["result"]["ok"] is True
    assert _raw.customers.find_one({"_id": CUST})["do_not_call"] is True
    print("  flag_do_not_call -> customer opted out")

    # --- 5. non-tool-call message is acknowledged, not processed ---
    body = {"message": {"type": "status-update", "call": {"id": "c1"}}}
    resp = await calls.vapi_webhook(_FakeRequest(body), db)
    assert resp == {"received": True}
    print("  status-update  -> acknowledged")

    _raw.calls.insert_one({
        "customer_id": CUST,
        "customer_name": "Test Customer",
        "phone": "+61400000000",
        "created_at": datetime.now(timezone.utc),
        "status": "queued",
        "vapi_call_id": "call-status-update",
        "dry_run": False,
        "compliance": {},
        "transcript": [],
    })
    body = {"message": {
        "type": "status-update",
        "status": "ended",
        "call": {"id": "call-status-update"},
    }}
    resp = await calls.vapi_webhook(_FakeRequest(body), db)
    assert resp == {"received": True}
    saved_call = _raw.calls.find_one({"vapi_call_id": "call-status-update"})
    assert saved_call["status"] == "ended"
    print("  status-update  -> persisted status")

    # --- 6. missing customer metadata -> graceful, no crash ---
    body = {"message": {"type": "tool-calls", "call": {"id": "c2"},
                        "toolCallList": [{"id": "tcX", "name": "resolve_item",
                                          "arguments": {"mention": "chips"}}]}}
    resp = await calls.vapi_webhook(_FakeRequest(body), db)
    assert resp["results"][0]["result"]["status"] == "ask"
    print("  no customer_id -> graceful 'ask'")

    # --- 7. unknown tool name -> error result, no crash ---
    body = _payload([{"id": "tcU", "name": "mystery_tool", "arguments": {}}])
    resp = await calls.vapi_webhook(_FakeRequest(body), db)
    assert "error" in resp["results"][0]["result"]
    print("  unknown tool   -> error result (no crash)")

    # --- 8. transcript lines are persisted for historical call detail ---
    _raw.calls.insert_one({
        "customer_id": CUST,
        "customer_name": "Test Customer",
        "phone": "+61400000000",
        "created_at": datetime.now(timezone.utc),
        "status": "queued",
        "vapi_call_id": "call-transcript",
        "dry_run": False,
        "compliance": {},
        "transcript": [],
    })
    body = {"message": {
        "type": "transcript",
        "transcriptType": "final",
        "role": "user",
        "transcript": "Can I get milk?",
        "timestamp": 123,
        "call": {"id": "call-transcript"},
    }}
    resp = await calls.vapi_webhook(_FakeRequest(body), db)
    assert resp == {"received": True}
    saved_call = _raw.calls.find_one({"vapi_call_id": "call-transcript"})
    assert saved_call["transcript"] == [{
        "role": "customer",
        "text": "Can I get milk?",
        "ts": 123,
    }]
    print("  transcript     -> persisted final line")

    # --- 8b. Vapi may encode final-only transcript filters in message.type ---
    _raw.calls.insert_one({
        "customer_id": CUST,
        "customer_name": "Test Customer",
        "phone": "+61400000000",
        "created_at": datetime.now(timezone.utc),
        "status": "queued",
        "vapi_call_id": "call-transcript-filtered-type",
        "dry_run": False,
        "compliance": {},
        "transcript": [],
    })
    body = {"message": {
        "type": 'transcript[transcriptType="final"]',
        "role": "assistant",
        "transcript": "Sure, anything else?",
        "timestamp": 124,
        "call": {"id": "call-transcript-filtered-type"},
    }}
    resp = await calls.vapi_webhook(_FakeRequest(body), db)
    assert resp == {"received": True}
    saved_call = _raw.calls.find_one({"vapi_call_id": "call-transcript-filtered-type"})
    assert saved_call["transcript"] == [{
        "role": "assistant",
        "text": "Sure, anything else?",
        "ts": 124,
    }]
    print("  transcript type -> final-only type accepted")

    # --- 8c. end-of-call report backfills final transcript and recording ---
    _raw.calls.insert_one({
        "customer_id": CUST,
        "customer_name": "Test Customer",
        "phone": "+61400000000",
        "created_at": datetime.now(timezone.utc),
        "status": "queued",
        "vapi_call_id": "call-end-report",
        "dry_run": False,
        "compliance": {},
        "transcript": [],
    })
    body = {"message": {
        "type": "end-of-call-report",
        "endedReason": "customer-ended-call",
        "call": {"id": "call-end-report"},
        "artifact": {
            "recordingUrl": "https://example.test/recording.wav",
            "messages": [
                {"role": "assistant", "message": "Hi there", "time": 0.5},
                {"role": "user", "message": "I need apples", "time": 2.0},
            ],
        },
    }}
    resp = await calls.vapi_webhook(_FakeRequest(body), db)
    assert resp == {"received": True}
    saved_call = _raw.calls.find_one({"vapi_call_id": "call-end-report"})
    assert saved_call["status"] == "ended"
    assert saved_call["ended_reason"] == "customer-ended-call"
    assert saved_call["recording_url"] == "https://example.test/recording.wav"
    assert saved_call["transcript"] == [
        {"role": "assistant", "text": "Hi there", "ts": 0.5},
        {"role": "customer", "text": "I need apples", "ts": 2.0},
    ]
    print("  end report      -> cached transcript and recording")

    # --- 9. Vapi artifacts normalize to dashboard transcript lines ---
    lines = vapi_client.extract_transcript_lines({
        "artifact": {
            "messages": [
                {"role": "bot", "message": "Hi there", "time": 0.5},
                {"role": "user", "message": "I need apples", "time": 2.0},
            ]
        }
    })
    assert lines == [
        {"role": "assistant", "text": "Hi there", "ts": 0.5},
        {"role": "customer", "text": "I need apples", "ts": 2.0},
    ]
    print("  vapi artifact  -> normalized transcript lines")

    recording_url = vapi_client.extract_recording_url({
        "artifact": {
            "recording": {"stereoUrl": "https://example.test/stereo.wav"},
            "recordingUrl": "https://example.test/mono.wav",
        }
    })
    assert recording_url == "https://example.test/mono.wav"
    print("  recording url  -> extracted from Vapi artifact")


asyncio.run(run())
print("\nALL WEBHOOK CHECKS PASSED")
