"""Test the resolve_item orchestrator — all four decision-tree branches.

mongomock is sync-only and lacks $text, so this uses the async adapter and
relies on the exact-alias path (not $text). Each branch is triggered by
deliberately shaped seed data.
"""
import asyncio
from datetime import datetime, timedelta, timezone

import mongomock
from bson import ObjectId

from app.services import item_resolver as ir
from app.services.item_resolver import RESOLVED, CONFIRM, RECOMMEND, ASK


# --- async adapter (mongomock sync -> async) --------------------------------
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


class _DB:
    def __init__(self, db): self._db = db
    def __getattr__(self, name): return _Coll(getattr(self._db, name))


# --- seed -------------------------------------------------------------------
_raw = mongomock.MongoClient()["test"]
CUST = ObjectId()

# Products: chips (3 brands) and milk (1 brand). Aliases drive resolution.
chips_smiths = ObjectId()
_raw.products.insert_many([
    {"_id": chips_smiths, "name": "Smith's Original Potato Chips 150g",
     "brand": "Smith's", "category": "Snacks", "subcategory": "Potato Chips",
     "aliases": ["chips", "crisps"], "size": "150g", "unit": "packet",
     "price": 4.5, "in_stock": True, "popularity_score": 90},
    {"_id": ObjectId(), "name": "Doritos Cheese Potato Chips 170g",
     "brand": "Doritos", "category": "Snacks", "subcategory": "Potato Chips",
     "aliases": ["chips", "crisps"], "size": "170g", "unit": "packet",
     "price": 5.0, "in_stock": True, "popularity_score": 70},
    {"_id": ObjectId(), "name": "Pauls Full Cream Milk 2L",
     "brand": "Pauls", "category": "Dairy", "subcategory": "Milk",
     "aliases": ["milk", "fresh milk"], "size": "2L", "unit": "bottle",
     "price": 3.5, "in_stock": True, "popularity_score": 60},
])

# brand_popularity: Doritos is the top chips brand. NOTE: no Milk row, so the
# milk no-history case will fall through to ASK.
_raw.brand_popularity.insert_many([
    {"category": "Snacks", "subcategory": "Potato Chips",
     "brand": "Doritos", "score": 100, "buyer_count": 8},
    {"category": "Snacks", "subcategory": "Potato Chips",
     "brand": "Smith's", "score": 60, "buyer_count": 5},
])

# order history: the customer bought Smith's chips before (for the CONFIRM case)
_raw.order_history.insert_one({
    "customer_id": CUST, "date": datetime.now(timezone.utc) - timedelta(days=20),
    "items": [{"product_id": chips_smiths, "name": "Smith's Original Potato Chips 150g",
               "category": "Snacks", "subcategory": "Potato Chips", "quantity": 2}],
})

db = _DB(_raw)
CUST_ID = str(CUST)
NEW_CUST = str(ObjectId())   # a customer with no history


async def run():
    # --- Branch A: brand named in the mention -> RESOLVED ---
    r = await ir.resolve_item(db, "Doritos chips", CUST_ID)
    assert r["status"] == RESOLVED, f"expected RESOLVED, got {r['status']}"
    assert r["product"]["brand"] == "Doritos"
    assert r["brand_source"] == "mentioned"
    print(f"  'Doritos chips'  -> {r['status']}: {r['product']['name']}")

    # --- Branch B: no brand, customer HAS history -> CONFIRM ---
    r = await ir.resolve_item(db, "chips", CUST_ID)
    assert r["status"] == CONFIRM, f"expected CONFIRM, got {r['status']}"
    assert r["product"]["name"].startswith("Smith's")
    assert r["brand_source"] == "history"
    print(f"  'chips' (has hx) -> {r['status']}: {r['message']}")

    # --- Branch C: no brand, no history -> RECOMMEND top brand ---
    r = await ir.resolve_item(db, "chips", NEW_CUST)
    assert r["status"] == RECOMMEND, f"expected RECOMMEND, got {r['status']}"
    assert r["brand"] == "Doritos", "should recommend the top-popularity brand"
    assert r["brand_source"] == "recommended"
    print(f"  'chips' (no hx)  -> {r['status']}: {r['message']}")

    # --- Branch D: no brand, no history, no popularity data -> ASK ---
    r = await ir.resolve_item(db, "milk", NEW_CUST)
    assert r["status"] == ASK, f"expected ASK, got {r['status']}"
    assert r["subcategory"] == "Milk"
    print(f"  'milk' (no data) -> {r['status']}: {r['message']}")

    # --- unresolvable mention -> ASK ---
    r = await ir.resolve_item(db, "xyzzy nonsense", NEW_CUST)
    assert r["status"] == ASK
    print(f"  'xyzzy nonsense' -> {r['status']} (couldn't identify)")

    # --- empty mention -> ASK ---
    r = await ir.resolve_item(db, "", CUST_ID)
    assert r["status"] == ASK
    print(f"  '' (empty)       -> {r['status']}")

    # --- branded mention but for a customer with history: brand wins ---
    # 'Smith's chips' should RESOLVE to Smith's, not CONFIRM from history.
    r = await ir.resolve_item(db, "Smith's chips", CUST_ID)
    assert r["status"] == RESOLVED, "explicit brand must take priority over history"
    assert r["product"]["brand"] == "Smith's"
    print(f"  'Smith's chips'  -> {r['status']} (explicit brand beats history)")


asyncio.run(run())
print("\nALL ORCHESTRATOR CHECKS PASSED")
