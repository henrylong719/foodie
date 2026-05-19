"""Test the customer history service.

Runs against mongomock with the async-cursor adapter (mongomock is sync-only).
Verifies subcategory-grained filtering, recency ordering, and the brand-
inference helper.
"""
import asyncio
from datetime import datetime, timedelta, timezone

import mongomock
from bson import ObjectId

from app.services import customer_history as ch


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


class _AsyncDB:
    def __init__(self, db):
        self._db = db

    @property
    def order_history(self):
        return _AsyncCollection(self._db.order_history)


# --- seed: one customer, three orders across two subcategories --------------
_raw = mongomock.MongoClient()["test"]
CUST = ObjectId()
now = datetime.now(timezone.utc)

_raw.order_history.insert_many([
    {  # oldest — Smith's chips
        "customer_id": CUST, "date": now - timedelta(days=60),
        "items": [{"product_id": ObjectId(), "name": "Smith's Original Potato Chips 150g",
                   "category": "Snacks", "subcategory": "Chips", "quantity": 2}],
    },
    {  # middle — chocolate (same category, different subcategory)
        "customer_id": CUST, "date": now - timedelta(days=30),
        "items": [{"product_id": ObjectId(), "name": "Cadbury Dairy Milk Chocolate 200g",
                   "category": "Snacks", "subcategory": "Chocolate", "quantity": 1}],
    },
    {  # newest — Doritos chips
        "customer_id": CUST, "date": now - timedelta(days=5),
        "items": [{"product_id": ObjectId(), "name": "Doritos Cheese Corn Chips 170g",
                   "category": "Snacks", "subcategory": "Chips", "quantity": 3}],
    },
])

db = _AsyncDB(_raw)
CUST_ID = str(CUST)


async def run():
    # --- 1. full history, most recent first ---
    allitems = await ch.get_history(db, CUST_ID)
    assert len(allitems) == 3, f"expected 3 items, got {len(allitems)}"
    assert allitems[0]["name"].startswith("Doritos"), "newest order should be first"
    print(f"  full history       -> {len(allitems)} items, newest first OK")

    # --- 2. subcategory filter must not bleed across subcategories ---
    chips = await ch.get_history(db, CUST_ID, subcategory="Chips")
    assert len(chips) == 2, f"expected 2 chip items, got {len(chips)}"
    assert all(i["subcategory"] == "Chips" for i in chips)
    print(f"  'Chips'            -> {len(chips)} items (chocolate excluded)")

    # --- 3. brand inference returns the MOST RECENT in the subcategory ---
    inferred = await ch.infer_brand_from_history(db, CUST_ID, "Chips")
    assert inferred is not None
    assert inferred["name"].startswith("Doritos"), "should infer most recent chips"
    print(f"  infer chips brand  -> {inferred['name']}")

    # --- 4. subcategory with no history -> None (caller falls back) ---
    none_result = await ch.infer_brand_from_history(db, CUST_ID, "Milk")
    assert none_result is None, "no Milk history should return None"
    print("  infer 'Milk' brand -> None (triggers popularity fallback)")

    # --- 5. unknown customer -> empty, not error ---
    assert await ch.get_history(db, str(ObjectId())) == []
    print("  unknown customer   -> [] ")

    # --- 6. malformed customer id -> empty, not crash ---
    assert await ch.get_history(db, "not-an-object-id") == []
    print("  malformed id       -> [] (no crash)")


asyncio.run(run())
print("\nALL CUSTOMER HISTORY CHECKS PASSED")
