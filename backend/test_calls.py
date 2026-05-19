"""Test the Vapi webhook: payload dispatch, results shape, all four tools.

Drives the webhook handler directly with realistic Vapi 'tool-calls' payloads.
mongomock + async adapter (sync-only, no $text).
"""
import asyncio
from datetime import datetime, timedelta, timezone

import mongomock
from bson import ObjectId

import app.routers.calls as calls


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
     "brand": "Smith's", "category": "Snacks", "subcategory": "Potato Chips",
     "aliases": ["chips"], "size": "150g", "unit": "packet",
     "price": 4.5, "in_stock": True, "popularity_score": 90},
    {"_id": ObjectId(), "name": "Doritos Cheese Potato Chips 170g",
     "brand": "Doritos", "category": "Snacks", "subcategory": "Potato Chips",
     "aliases": ["chips"], "size": "170g", "unit": "packet",
     "price": 5.0, "in_stock": True, "popularity_score": 70},
])
_raw.brand_popularity.insert_one({
    "category": "Snacks", "subcategory": "Potato Chips",
    "brand": "Doritos", "score": 100, "buyer_count": 8})
_raw.order_history.insert_one({
    "customer_id": CUST, "date": datetime.now(timezone.utc) - timedelta(days=10),
    "items": [{"product_id": chips_id, "name": "Smith's Original Potato Chips 150g",
               "category": "Snacks", "subcategory": "Potato Chips", "quantity": 1}]})

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
         "arguments": {"subcategory": "Potato Chips", "brand": "Smith's"}},
    ])
    resp = await calls.vapi_webhook(_FakeRequest(body), db)
    assert len(resp["results"]) == 2, "both tool calls must be answered"
    ids = {r["toolCallId"] for r in resp["results"]}
    assert ids == {"tcA", "tcB"}
    print(f"  batch of 2     -> {len(resp['results'])} results, ids match")

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


asyncio.run(run())
print("\nALL WEBHOOK CHECKS PASSED")
