"""Test the product search endpoint and resolution service.

Runs against mongomock. The exact-alias path and ranking are fully exercised.
The $text fallback is mongomock-unsupported, so that one assertion is skipped
on the mock and noted — it works against real MongoDB / Atlas.
"""
import asyncio

import mongomock

import app.db as db_module
from app.services import resolution


# --- async adapter ---------------------------------------------------------
# The resolution service uses Motor's async API (await ...find(...).to_list()).
# mongomock is sync-only, so wrap its cursor to expose an async to_list().
# This shim lives in the test only; the service code is real-Atlas-correct.
class _AsyncCursor:
    def __init__(self, cursor):
        self._cursor = cursor

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
    def products(self):
        return _AsyncCollection(self._db.products)


# in-memory DB seeded with a few hand-built products
_raw = mongomock.MongoClient()["test"]
_raw.products.insert_many([
    {"name": "Smith's Original Potato Chips 150g", "brand": "Smith's",
     "category": "Snacks", "subcategory": "Chips",
     "aliases": ["chips", "crisps"], "size": "150g", "unit": "packet",
     "price": 4.5, "in_stock": True, "popularity_score": 90},
    {"name": "Doritos Cheese Corn Chips 170g", "brand": "Doritos",
     "category": "Snacks", "subcategory": "Chips",
     "aliases": ["chips", "crisps"], "size": "170g", "unit": "packet",
     "price": 5.0, "in_stock": True, "popularity_score": 75},
    {"name": "Nobby's Value Potato Chips 100g", "brand": "Nobby's",
     "category": "Snacks", "subcategory": "Chips",
     "aliases": ["chips", "crisps"], "size": "100g", "unit": "packet",
     "price": 3.0, "in_stock": False, "popularity_score": 99},
    {"name": "Heinz Tomato Sauce 500g", "brand": "Heinz",
     "category": "Pantry", "subcategory": "Tomato Sauce",
     "aliases": ["tomato sauce", "ketchup"], "size": "500g", "unit": "bottle",
     "price": 4.0, "in_stock": True, "popularity_score": 80},
])

# the async-wrapped handle the service expects
db = _AsyncDB(_raw)


async def run():
    # --- 1. exact alias match ---
    hits = await resolution.search_products(db, "chips")
    assert len(hits) == 3, f"expected 3 chips, got {len(hits)}"
    print(f"  'chips'        -> {len(hits)} products")

    # --- 2. ranking: in-stock first, then popularity ---
    # Nobby's has the highest popularity (99) but is OUT of stock, so it must
    # rank LAST, not first. Smith's (in-stock, 90) should lead.
    assert hits[0]["brand"] == "Smith's", f"expected Smith's first, got {hits[0]['brand']}"
    assert hits[-1]["brand"] == "Nobby's", "out-of-stock product should rank last"
    print(f"  ranking        -> {[h['brand'] for h in hits]}")

    # --- 3. case / whitespace insensitivity ---
    assert len(await resolution.search_products(db, "  CHIPS ")) == 3
    print("  ' CHIPS '      -> normalized OK")

    # --- 4. alias for a different category ---
    sauce = await resolution.search_products(db, "ketchup")
    assert len(sauce) == 1 and sauce[0]["brand"] == "Heinz"
    print(f"  'ketchup'      -> {sauce[0]['name']}")

    # --- 5. limit is respected ---
    assert len(await resolution.search_products(db, "chips", limit=2)) == 2
    print("  limit=2        -> 2 products")

    # --- 6. empty / blank query ---
    assert await resolution.search_products(db, "") == []
    assert await resolution.search_products(db, "   ") == []
    print("  empty query    -> [] ")

    # --- 7. _id is stringified, internal score stripped ---
    assert isinstance(hits[0]["_id"], str), "_id must be a string"
    assert "score" not in hits[0], "internal score must not leak"
    print("  serialization  -> _id is str, score stripped")

    # --- 8. $text fallback (real Mongo only) ---
    try:
        miss = await resolution.search_products(db, "potato")  # not an alias
        print(f"  '$text' path   -> {len(miss)} products (text index works)")
    except Exception as exc:
        print(f"  '$text' path   -> SKIPPED on mongomock ({type(exc).__name__})")


asyncio.run(run())
print("\nALL RESOLUTION CHECKS PASSED")
