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
     "brand": "Smith's", "category": "Snacks", "subcategory": "Chips",
     "brand_aliases": ["smiths"],
     "aliases": ["chips", "crisps"], "size": "150g", "unit": "packet",
     "price": 4.5, "in_stock": True, "popularity_score": 90},
    {"_id": ObjectId(), "name": "Doritos Cheese Corn Chips 170g",
     "brand": "Doritos", "category": "Snacks", "subcategory": "Chips",
     "brand_aliases": [],
     "aliases": ["chips", "crisps"], "size": "170g", "unit": "packet",
     "price": 5.0, "in_stock": True, "popularity_score": 70},
    {"_id": ObjectId(), "name": "Pauls Full Cream Milk 2L",
     "brand": "Pauls", "category": "Dairy", "subcategory": "Milk",
     "brand_aliases": [],
     "aliases": ["milk", "fresh milk"], "size": "2L", "unit": "bottle",
     "price": 3.5, "in_stock": True, "popularity_score": 60},
    {"_id": ObjectId(), "name": "Coca-Cola Classic Soft Drink 1.25L",
     "brand": "Coca-Cola", "category": "Beverages", "subcategory": "Soft Drink",
     "brand_aliases": ["coca cola", "coca-cola"],
     "aliases": ["soft drink", "soda", "coke", "cola"], "size": "1.25L",
     "unit": "bottle", "price": 3.0, "in_stock": True,
     "popularity_score": 80},
    {"_id": ObjectId(), "name": "Schweppes Lemonade Soft Drink 1.25L",
     "brand": "Schweppes", "category": "Beverages", "subcategory": "Soft Drink",
     "brand_aliases": [],
     "aliases": ["soft drink", "soda", "cola"], "size": "1.25L",
     "unit": "bottle", "price": 2.8, "in_stock": True,
     "popularity_score": 50},
    {"_id": ObjectId(), "name": "Red Bull Original Energy Drink 250ml",
     "brand": "Red Bull", "category": "Beverages", "subcategory": "Energy Drink",
     "brand_aliases": ["redbull"],
     "aliases": ["energy drink"], "size": "250ml", "unit": "can",
     "price": 4.0, "in_stock": True, "popularity_score": 70},
    {"_id": ObjectId(), "name": "Arnott's Original Crackers 250g",
     "brand": "Arnott's", "category": "Snacks", "subcategory": "Crackers",
     "brand_aliases": ["arnotts"],
     "aliases": ["crackers"], "size": "250g", "unit": "packet",
     "price": 4.2, "in_stock": True, "popularity_score": 65},
    {"_id": ObjectId(), "name": "Bakers Delight Classic Bread 650g",
     "brand": "Bakers Delight", "category": "Bakery", "subcategory": "Bread",
     "brand_aliases": ["bakers"],
     "aliases": ["bread", "loaf"], "size": "650g", "unit": "loaf",
     "price": 5.5, "in_stock": True, "popularity_score": 55},
])

# brand_popularity: Doritos is the top chips brand. NOTE: no Milk row, so the
# milk no-history case will fall through to ASK.
_raw.brand_popularity.insert_many([
    {"category": "Snacks", "subcategory": "Chips",
     "brand": "Doritos", "score": 100, "buyer_count": 8},
    {"category": "Snacks", "subcategory": "Chips",
     "brand": "Smith's", "score": 60, "buyer_count": 5},
    {"category": "Beverages", "subcategory": "Soft Drink",
     "brand": "Coca-Cola", "score": 100, "buyer_count": 12},
    {"category": "Beverages", "subcategory": "Soft Drink",
     "brand": "Schweppes", "score": 50, "buyer_count": 6},
])

# order history: the customer bought Smith's chips before (for the CONFIRM case)
_raw.order_history.insert_one({
    "customer_id": CUST, "date": datetime.now(timezone.utc) - timedelta(days=20),
    "items": [{"product_id": chips_smiths, "name": "Smith's Original Potato Chips 150g",
               "category": "Snacks", "subcategory": "Chips", "quantity": 2}],
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
    assert r["available_brands"] == ["Doritos", "Smith's"]
    assert r["next_tool"] == "resolve_brand"
    print(f"  'chips' (has hx) -> {r['status']}: {r['message']}")

    # --- Branch C: no brand, no history -> RECOMMEND top brand ---
    r = await ir.resolve_item(db, "chips", NEW_CUST)
    assert r["status"] == RECOMMEND, f"expected RECOMMEND, got {r['status']}"
    assert r["brand"] == "Doritos", "should recommend the top-popularity brand"
    assert r["product"]["brand"] == "Doritos"
    assert r["product"]["name"] == "Doritos chips"
    assert r["available_brands"] == ["Doritos", "Smith's"]
    assert r["brand_source"] == "recommended"
    print(f"  'chips' (no hx)  -> {r['status']}: {r['message']}")

    # --- Branch D: no brand, no history, no popularity data -> ASK ---
    r = await ir.resolve_item(db, "milk", NEW_CUST)
    assert r["status"] == ASK, f"expected ASK, got {r['status']}"
    assert r["subcategory"] == "Milk"
    assert r["next_tool"] == "resolve_brand"
    print(f"  'milk' (no data) -> {r['status']}: {r['message']}")

    r = await ir.resolve_brand(db, "Milk", "Pauls")
    assert r["status"] == RESOLVED, f"expected RESOLVED, got {r['status']}"
    assert r["product"]["brand"] == "Pauls"
    print(f"  'Pauls' milk     -> {r['status']} (brand answer resolved)")

    # --- Brand answer with a near-miss STT spelling should still resolve ---
    peters = ObjectId()
    _raw.products.insert_one(
        {"_id": peters, "name": "Peters Classic Ice Cream 2L",
         "brand": "Peters", "category": "Frozen", "subcategory": "Ice Cream",
         "brand_aliases": [], "aliases": ["ice cream", "icecream"],
         "size": "2L", "unit": "tub", "price": 8.0, "in_stock": True,
         "popularity_score": 55}
    )
    r = await ir.resolve_brand(db, "Ice Cream", "Perters")
    assert r["status"] == RESOLVED, f"expected RESOLVED, got {r['status']}"
    assert r["product"]["brand"] == "Peters"
    print(f"  'Perters' ice cream -> {r['status']} (near-miss brand spelling)")

    r = await ir.resolve_brand(db, "Ice Cream", "Peters ice cream")
    assert r["status"] == RESOLVED, f"expected RESOLVED, got {r['status']}"
    assert r["product"]["brand"] == "Peters"
    print(f"  'Peters ice cream' -> {r['status']} (brand answer with item context)")

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

    # --- generic "Coke" should identify the item class, not force Coca-Cola ---
    r = await ir.resolve_item(db, "Coke", NEW_CUST)
    assert r["status"] == RECOMMEND, f"expected RECOMMEND, got {r['status']}"
    assert r["brand"] == "Coca-Cola"
    assert r["subcategory"] == "Soft Drink"
    assert r["brand_source"] == "recommended"
    print(f"  'Coke'           -> {r['status']} (generic soft drink request)")

    r = await ir.resolve_brand(db, "Soft Drink", "Coca Cola")
    assert r["status"] == RESOLVED, f"expected RESOLVED, got {r['status']}"
    assert r["product"]["brand"] == "Coca-Cola"
    print(f"  'Coca Cola'      -> {r['status']} (hyphen-insensitive)")

    r = await ir.resolve_brand(db, "Soft Drink", "Coke")
    assert r["status"] == ASK, f"expected ASK, got {r['status']}"
    assert "product" not in r
    print(f"  'Coke' brand     -> {r['status']} (ambiguous brand answer)")

    r = await ir.resolve_brand(db, "Soft Drink", "Red Bull")
    assert r["status"] == ASK, f"expected ASK, got {r['status']}"
    assert r["alternate_product"]["brand"] == "Red Bull"
    assert r["alternate_subcategory"] == "Energy Drink"
    assert "Coca-Cola" in r["available_brands"]
    print("  'Red Bull' soft drink -> ask with energy drink alternate")

    # --- unknown subcategory (agent hallucination) -> ASK, no brand list ---
    r = await ir.resolve_brand(db, "Cookies", "Arnott's")
    assert r["status"] == ASK, f"expected ASK, got {r['status']}"
    assert r["available_brands"] == [], "must not surface brands for unknown subcategory"
    assert "product" not in r
    assert "Cookies" in r["message"], "message should name the unknown subcategory"
    print(f"  'Cookies'/Arnott -> {r['status']} (unknown subcategory)")

    r = await ir.resolve_item(db, "Smiths chips", CUST_ID)
    assert r["status"] == RESOLVED, "apostrophe-free brand should resolve"
    assert r["product"]["brand"] == "Smith's"
    print(f"  'Smiths chips'   -> {r['status']} (punctuation-insensitive)")

    r = await ir.resolve_brand(db, "Crackers", "arnotts")
    assert r["status"] == RESOLVED, f"expected RESOLVED, got {r['status']}"
    assert r["product"]["brand"] == "Arnott's"
    print(f"  'arnotts'        -> {r['status']} (catalog brand alias)")

    r = await ir.resolve_item(db, "bakers bread", NEW_CUST)
    assert r["status"] == RESOLVED, f"expected RESOLVED, got {r['status']}"
    assert r["product"]["brand"] == "Bakers Delight"
    print(f"  'bakers bread'   -> {r['status']} (catalog brand alias)")

    # --- branded mention but every product for that brand is OOS ---
    # Must NOT RESOLVE to an unfulfillable SKU. Falls through to the next
    # fallback (history CONFIRM for this customer with Smith's history).
    _raw.products.update_many({"brand": "Doritos"}, {"$set": {"in_stock": False}})
    r = await ir.resolve_item(db, "Doritos chips", CUST_ID)
    assert r["status"] != RESOLVED or r["product"].get("in_stock"), (
        f"must not RESOLVE to OOS product, got {r['status']} for "
        f"{r.get('product')}"
    )
    assert r["status"] == CONFIRM, f"expected fallback to CONFIRM, got {r['status']}"
    assert r["product"]["name"].startswith("Smith's"), \
        f"expected Smith's history fallback, got {r['product']['name']}"
    print(f"  'Doritos' all OOS -> {r['status']} (skips OOS, falls back)")

    # --- top-popularity brand is OOS: RECOMMEND should skip to next brand ---
    # NEW_CUST has no history, so 2c is the path. Doritos is the top brand
    # by popularity but fully OOS, so we should recommend Smith's instead.
    r = await ir.resolve_item(db, "chips", NEW_CUST)
    assert r["status"] == RECOMMEND, f"expected RECOMMEND, got {r['status']}"
    assert r["brand"] == "Smith's", \
        f"top OOS brand should be skipped; got {r['brand']}"
    assert r["product"]["brand"] == "Smith's"
    assert r["product"].get("in_stock"), "recommended product must be in stock"
    print(f"  'chips' top OOS  -> {r['status']} (skips OOS brand, recommends next)")
    _raw.products.update_many({"brand": "Doritos"}, {"$set": {"in_stock": True}})

    # --- brand-only mention ("Doritos") should pivot to that brand's
    # subcategory and resolve, not fall through to ASK. ---
    r = await ir.resolve_item(db, "Doritos", NEW_CUST)
    assert r["status"] == RESOLVED, f"expected RESOLVED, got {r['status']}"
    assert r["product"]["brand"] == "Doritos"
    assert r["subcategory"] == "Chips"
    print(f"  'Doritos'        -> {r['status']} (brand-only mention)")

    # multi-word brand alias ("Red Bull") should also resolve brand-only
    r = await ir.resolve_item(db, "Red Bull", NEW_CUST)
    assert r["status"] == RESOLVED, f"expected RESOLVED, got {r['status']}"
    assert r["product"]["brand"] == "Red Bull"
    assert r["subcategory"] == "Energy Drink"
    print(f"  'Red Bull'       -> {r['status']} (multi-word brand-only)")


asyncio.run(run())
print("\nALL ORCHESTRATOR CHECKS PASSED")
