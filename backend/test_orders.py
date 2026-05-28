"""Test save_order input validation.

mongomock + async adapter; covers the invariants the Vapi tool layer relies on:
quantity must be a positive int and product_id must point at a real product.
"""
import asyncio

import mongomock
from bson import ObjectId

from app.services import orders


# --- async adapter (mongomock is sync-only; service uses Motor async API) ---
class _AsyncCursor:
    def __init__(self, cursor):
        self._cursor = cursor

    def sort(self, *args, **kwargs):
        return _AsyncCursor(self._cursor.sort(*args, **kwargs))

    async def to_list(self, length=None):
        docs = list(self._cursor)
        return docs[:length] if length is not None else docs


class _AsyncCollection:
    def __init__(self, collection):
        self._c = collection

    def find(self, *args, **kwargs):
        return _AsyncCursor(self._c.find(*args, **kwargs))

    async def find_one(self, *args, **kwargs):
        return self._c.find_one(*args, **kwargs)

    async def insert_one(self, *args, **kwargs):
        return self._c.insert_one(*args, **kwargs)


class _AsyncDB:
    def __init__(self, db):
        self._db = db

    def __getattr__(self, name):
        return _AsyncCollection(getattr(self._db, name))


# --- seed: one customer, two products ---------------------------------------
_raw = mongomock.MongoClient()["test"]
CUST = ObjectId()
PROD = ObjectId()
PROD2 = ObjectId()
_raw.products.insert_one({
    "_id": PROD, "name": "Smith's Original Potato Chips 150g",
    "brand": "Smith's", "category": "Snacks", "subcategory": "Chips",
    "price": 4.5, "in_stock": True,
})
_raw.products.insert_one({
    "_id": PROD2, "name": "Pauls Full Cream Milk 2L",
    "brand": "Pauls", "category": "Dairy", "subcategory": "Milk",
    "price": 4.0, "in_stock": True,
})
_raw.customers.insert_one({"_id": CUST, "name": "Alex Customer"})
db = _AsyncDB(_raw)


def _item(**over):
    base = {"product_id": str(PROD), "name": "Smith's", "quantity": 2,
            "brand_source": "history"}
    base.update(over)
    return base


async def run():
    # --- 1. happy path persists the order ---
    res = await orders.save_order(db, str(CUST), "call-ok", [_item()])
    assert res["ok"] is True
    saved = _raw.captured_orders.find_one({"_id": ObjectId(res["order_id"])})
    assert saved["items"][0]["quantity"] == 2
    assert saved["items"][0]["product_id"] == str(PROD)
    print("  happy path     -> order persisted")

    # --- 2. transcript_url is ignored; call transcripts live on call records ---
    res = await orders.save_order(
        db,
        str(CUST),
        "call-transcript-url",
        [_item()],
        "javascript:alert(1)",
    )
    assert res["ok"] is True
    saved = _raw.captured_orders.find_one({"_id": ObjectId(res["order_id"])})
    assert saved["transcript_url"] is None
    print("  transcript_url -> ignored")

    # --- 3. unknown product_id is rejected (the C2 finding) ---
    res = await orders.save_order(
        db, str(CUST), "call-x",
        [_item(product_id=str(ObjectId()), quantity=-3)],
    )
    assert res["ok"] is False
    assert "quantity" in res["error"], "negative quantity is checked first"
    print("  negative qty   -> rejected")

    # --- 4. non-numeric quantity ("two") no longer raises ---
    res = await orders.save_order(db, str(CUST), "call-x", [_item(quantity="two")])
    assert res["ok"] is False
    assert "invalid quantity" in res["error"]
    print("  non-numeric qty -> rejected")

    # --- 5. zero quantity rejected ---
    res = await orders.save_order(db, str(CUST), "call-x", [_item(quantity=0)])
    assert res["ok"] is False
    assert "positive" in res["error"]
    print("  zero qty       -> rejected")

    # --- 6. bool quantity is not silently coerced to 1/0 ---
    res = await orders.save_order(db, str(CUST), "call-x", [_item(quantity=True)])
    assert res["ok"] is False
    assert "invalid quantity" in res["error"]
    print("  bool qty       -> rejected")

    # --- 7. unknown product_id with otherwise-valid item ---
    phantom = str(ObjectId())
    res = await orders.save_order(db, str(CUST), "call-x", [_item(product_id=phantom)])
    assert res["ok"] is False
    assert "unknown product" in res["error"]
    print("  unknown product -> rejected")

    # --- 8. malformed product_id (not an ObjectId) ---
    res = await orders.save_order(db, str(CUST), "call-x", [_item(product_id="deadbeef")])
    assert res["ok"] is False
    assert "unknown product" in res["error"]
    print("  bad product_id -> rejected")

    # --- 8b. bad product_id but exact name match recovers ---
    # LLMs occasionally fabricate product_ids at recap time. When the spoken
    # name still matches a real product, save_order recovers rather than
    # killing the whole call. This is the bug fix path.
    res = await orders.save_order(
        db, str(CUST), "call-recover",
        [_item(product_id=phantom, name="Smith's Original Potato Chips 150g")],
    )
    assert res["ok"] is True, res
    saved = _raw.captured_orders.find_one({"call_id": "call-recover"})
    assert saved["items"][0]["product_id"] == str(PROD)
    print("  bad id + good name -> recovered by name lookup")

    # --- 9. one bad item rejects the whole batch (no partial save) ---
    before = _raw.captured_orders.count_documents({"call_id": "call-mixed"})
    res = await orders.save_order(db, str(CUST), "call-mixed", [
        _item(),
        _item(product_id=str(ObjectId())),  # unknown
    ])
    assert res["ok"] is False
    after = _raw.captured_orders.count_documents({"call_id": "call-mixed"})
    assert before == after, "no order document should be created on rejection"
    print("  mixed batch    -> all-or-nothing")

    # --- 10. duplicate save_order for the same call_id is idempotent ---
    # Tool-calling LLMs sometimes re-invoke save_order on retry; a second call
    # for the same call_id must NOT create a second captured_orders row.
    res1 = await orders.save_order(db, str(CUST), "call-dup", [_item()])
    assert res1["ok"] is True
    res2 = await orders.save_order(db, str(CUST), "call-dup", [_item()])
    assert res2["ok"] is True
    assert res2["order_id"] == res1["order_id"], "retry must return original order_id"
    assert _raw.captured_orders.count_documents({"call_id": "call-dup"}) == 1, \
        "exactly one row per call_id"
    print("  duplicate call -> idempotent (one row)")

    # --- 11. get_order returns customer_name and item_count (the bug fix) ---
    created = await orders.save_order(
        db, str(CUST), "call-get",
        [_item(), _item(product_id=str(PROD2), name="Pauls", quantity=3)],
    )
    fetched = await orders.get_order(db, created["order_id"])
    assert fetched is not None
    assert fetched["customer_name"] == "Alex Customer"
    assert fetched["item_count"] == 2
    assert fetched["_id"] == created["order_id"]
    assert fetched["customer_id"] == str(CUST)
    print("  get_order      -> joins customer_name + item_count")

    # --- 12. get_order returns None for invalid / missing ids ---
    assert await orders.get_order(db, "not-an-objectid") is None
    assert await orders.get_order(db, str(ObjectId())) is None
    print("  get_order 404  -> invalid/missing -> None")

    # --- 13. recap correction: duplicate product_id, last-write-wins ---
    # Script 9: customer asks for chips qty 2, then on recap says "make it 3".
    # If the LLM emits both lines in one save_order call, the corrected
    # quantity must win and the order must contain one chips row, not two.
    res = await orders.save_order(
        db, str(CUST), "call-recap-fix",
        [
            _item(quantity=2),
            _item(product_id=str(PROD2), name="Pauls", quantity=1),
            _item(quantity=3),
        ],
    )
    assert res["ok"] is True
    saved = _raw.captured_orders.find_one({"_id": ObjectId(res["order_id"])})
    by_pid = {it["product_id"]: it for it in saved["items"]}
    assert len(saved["items"]) == 2, "duplicate chips collapse to one row"
    assert by_pid[str(PROD)]["quantity"] == 3, "chips: last write wins"
    assert by_pid[str(PROD2)]["quantity"] == 1, "milk untouched"
    print("  recap correction -> last-write-wins per item")


asyncio.run(run())
print("\nALL ORDER CHECKS PASSED")
