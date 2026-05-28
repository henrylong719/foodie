"""Test the Vapi webhook: payload dispatch, results shape, all four tools.

Drives the webhook handler directly with realistic Vapi 'tool-calls' payloads.
mongomock + async adapter (sync-only, no $text).
"""
import asyncio
from datetime import datetime, timedelta, timezone

import mongomock
from bson import ObjectId

import app.routers.calls as calls
from app.services import call_service, vapi_client


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
    # --- 0a. tool debug summaries preserve the fields needed for diagnosis ---
    summary = calls._summarize_tool_result({
        "status": "ask",
        "subcategory": "Ice Cream",
        "message": "Sorry, we don't have Peters in ice cream.",
        "available_brands": ["Streets", "Bulla", "Peters"],
        "product": {"brand": "Peters", "name": "Peters Classic Ice Cream 500g"},
    })
    assert summary == {
        "status": "ask",
        "message": "Sorry, we don't have Peters in ice cream.",
        "subcategory": "Ice Cream",
        "available_brands": ["Streets", "Bulla", "Peters"],
        "product": {
            "brand": "Peters",
            "name": "Peters Classic Ice Cream 500g",
        },
    }
    print("  tool summary    -> debug fields preserved")

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
    assert saved["status"] == "pending_fulfillment"
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

    # --- 6. missing customer metadata (inbound, unknown caller) -> still
    #        resolves to a usable result, just without the history path ---
    body = {"message": {"type": "tool-calls", "call": {"id": "c2"},
                        "toolCallList": [{"id": "tcX", "name": "resolve_item",
                                          "arguments": {"mention": "chips"}}]}}
    resp = await calls.vapi_webhook(_FakeRequest(body), db)
    result = resp["results"][0]["result"]
    # without a customer, the history-based "confirm" branch is skipped; the
    # resolver should still return a real status (recommend / resolved / ask)
    # with a subcategory the agent can use.
    assert result["status"] in {"resolved", "recommend", "ask"}
    assert "confirm" != result["status"], "history path requires customer_id"
    print(f"  no customer_id -> graceful '{result['status']}' (no history path)")

    # --- 6b. inbound call with a known caller number resolves customer_id ---
    body = {"message": {"type": "tool-calls",
                        "call": {"id": "c2b",
                                 "customer": {"number": "+61400000000"}},
                        "toolCallList": [{"id": "tcXb", "name": "resolve_item",
                                          "arguments": {"mention": "chips"}}]}}
    resp = await calls.vapi_webhook(_FakeRequest(body), db)
    result = resp["results"][0]["result"]
    assert result["status"] in {"resolved", "confirm", "recommend", "ask"}
    print(f"  inbound caller -> identified, status '{result['status']}'")

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

    # --- 8d. transcript for an unknown call_id upserts a stub --------------
    # Without the upsert, the line is silently dropped (live SSE sees it,
    # but the DB doesn't), so call detail is empty on reload.
    body = {"message": {
        "type": "transcript",
        "transcriptType": "final",
        "role": "user",
        "transcript": "Hello?",
        "timestamp": 125,
        "call": {"id": "call-unknown-id"},
    }}
    resp = await calls.vapi_webhook(_FakeRequest(body), db)
    assert resp == {"received": True}
    saved_call = _raw.calls.find_one({"vapi_call_id": "call-unknown-id"})
    assert saved_call is not None, "stub record must be created on unknown call_id"
    assert saved_call["transcript"] == [
        {"role": "customer", "text": "Hello?", "ts": 125}
    ]
    assert saved_call["status"] == "unknown"
    print("  transcript      -> upsert persists line for unknown call_id")

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

    lines = vapi_client.extract_transcript_lines({
        "artifact": {
            "messagesOpenAIFormatted": [
                {"role": "assistant", "content": "Hi there"},
                {"role": "user", "content": "I need apples"},
                {
                    "role": "assistant",
                    "content": "Anything else?",
                    "timestamp": 4.5,
                },
            ]
        }
    })
    assert lines == [
        {"role": "assistant", "text": "Hi there"},
        {"role": "customer", "text": "I need apples"},
        {"role": "assistant", "text": "Anything else?", "ts": 4.5},
    ]
    print("  openai artifact -> preserves only real timestamps")

    recording_url = vapi_client.extract_recording_url({
        "artifact": {
            "recording": {"stereoUrl": "https://example.test/stereo.wav"},
            "recordingUrl": "https://example.test/mono.wav",
        }
    })
    assert recording_url == "https://example.test/stereo.wav", (
        "stereo must win over mono regardless of nesting"
    )

    # top-level stereo still wins over nested stereo (both are stereo; either is fine,
    # but top-level is canonical per Vapi's schema).
    recording_url = vapi_client.extract_recording_url({
        "artifact": {
            "stereoRecordingUrl": "https://example.test/top-stereo.wav",
            "recording": {"stereoUrl": "https://example.test/nested-stereo.wav"},
        }
    })
    assert recording_url == "https://example.test/top-stereo.wav"

    # mono-only payload falls back to recordingUrl.
    recording_url = vapi_client.extract_recording_url({
        "artifact": {"recordingUrl": "https://example.test/mono-only.wav"}
    })
    assert recording_url == "https://example.test/mono-only.wav"
    print("  recording url  -> stereo preferred, mono fallback")


asyncio.run(run())


# --- place_outbound_call dedupe --------------------------------------------
async def run_dedupe():
    """A rapid second POST /calls must NOT place a second Vapi call.

    Covers the bug where /calls/new re-fires placeCall on StrictMode remount,
    page refresh, or browser back/fwd. The dedupe collapses any retry within
    DEDUPE_WINDOW_SECONDS to the in-flight queued call.
    """
    raw2 = mongomock.MongoClient()["dedupe_test"]
    cust2 = ObjectId()
    raw2.customers.insert_one({
        "_id": cust2, "name": "Dedupe Customer", "phone": "+61400111222",
        "do_not_call": False, "consent": {"given": True},
        "preferred_language": "en",
    })
    db2 = _DB(raw2)

    placed = []

    async def fake_place_call(customer_id, phone_number, *, client=None):
        placed.append({"customer_id": customer_id, "phone_number": phone_number})
        return {
            "call_id": f"vapi-{len(placed)}",
            "status": "queued",
            "dry_run": True,
            "provider_status": "simulated",
        }

    original = vapi_client.place_call
    vapi_client.place_call = fake_place_call
    try:
        first = await call_service.place_outbound_call(db2, str(cust2))
        second = await call_service.place_outbound_call(db2, str(cust2))

        assert first["ok"] is True
        assert second["ok"] is True
        assert second["call_id"] == first["call_id"], \
            "dedupe must return the in-flight call_id"
        assert second["call_record_id"] == first["call_record_id"]
        assert second.get("deduped") is True
        assert len(placed) == 1, \
            f"Vapi must be called once, got {len(placed)}"
        assert raw2.calls.count_documents({}) == 1, \
            "only one call record should be written"
        print(f"  dedupe          -> 2 POSTs -> 1 Vapi call, 1 record")

        # Outside the dedupe window, a fresh POST proceeds.
        stale = datetime.now(timezone.utc) - timedelta(
            seconds=call_service.DEDUPE_WINDOW_SECONDS + 5
        )
        raw2.calls.update_one({}, {"$set": {"created_at": stale}})

        third = await call_service.place_outbound_call(db2, str(cust2))
        assert third["ok"] is True
        assert third.get("deduped") is not True, \
            "expired window must not dedupe"
        assert len(placed) == 2
        assert raw2.calls.count_documents({}) == 2
        print("  dedupe window   -> expires after DEDUPE_WINDOW_SECONDS")
    finally:
        vapi_client.place_call = original


asyncio.run(run_dedupe())


# --- transcript-before-record race -----------------------------------------
async def run_transcript_race():
    """A transcript event that lands before place_outbound_call's write must
    merge into the same record, not create a duplicate."""
    raw3 = mongomock.MongoClient()["race_test"]
    cust3 = ObjectId()
    raw3.customers.insert_one({
        "_id": cust3, "name": "Race Customer", "phone": "+61400000111",
        "do_not_call": False, "consent": {"given": True},
        "preferred_language": "en",
    })
    db3 = _DB(raw3)

    # Simulate Vapi pushing a transcript line before insert_one runs.
    await call_service.append_transcript_line(db3, "vapi-race-1", {
        "role": "customer", "text": "Are you there?", "ts": 0,
    })
    assert raw3.calls.count_documents({}) == 1, "stub must be created"

    async def fake_place_call(customer_id, phone_number, *, client=None):
        return {
            "call_id": "vapi-race-1",
            "status": "queued",
            "dry_run": True,
            "provider_status": "simulated",
        }

    original = vapi_client.place_call
    vapi_client.place_call = fake_place_call
    try:
        result = await call_service.place_outbound_call(db3, str(cust3))
        assert result["ok"] is True
        assert result["call_id"] == "vapi-race-1"
        assert raw3.calls.count_documents({}) == 1, \
            "race must merge into the stub, not duplicate"

        saved = raw3.calls.find_one({"vapi_call_id": "vapi-race-1"})
        assert saved["status"] == "queued"
        assert saved["customer_id"] == cust3
        assert saved["customer_name"] == "Race Customer"
        assert saved["transcript"] == [
            {"role": "customer", "text": "Are you there?", "ts": 0}
        ], "transcript pushed before place_outbound_call must survive"
        print("  race merge      -> early transcript merged into call record")
    finally:
        vapi_client.place_call = original


asyncio.run(run_transcript_race())
print("\nALL WEBHOOK CHECKS PASSED")
