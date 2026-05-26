"""Integration test for the $text fallback in resolution.search_products.

mongomock doesn't implement $text, so test_resolution.py can only exercise
the exact-alias path. This test runs against a real MongoDB to cover the
fallback. Skipped (exit 0) if MONGODB_URI is unset, so it's a no-op in
environments without a Mongo instance.
"""
import asyncio
import os
import sys
import uuid

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import TEXT

from app.services import resolution


async def run(uri: str) -> None:
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=3000)
    # Use a unique DB per run so parallel/repeat runs don't collide and we
    # never touch the developer's real data.
    db_name = f"foodie_test_{uuid.uuid4().hex[:8]}"
    db = client[db_name]
    try:
        await db.products.insert_many([
            {"name": "Smith's Original Potato Chips 150g", "brand": "Smith's",
             "category": "Snacks", "subcategory": "Chips",
             "aliases": ["chips"], "in_stock": True, "popularity_score": 90},
            {"name": "Nobby's Value Potato Chips 100g", "brand": "Nobby's",
             "category": "Snacks", "subcategory": "Chips",
             "aliases": ["chips"], "in_stock": False, "popularity_score": 99},
            {"name": "Heinz Tomato Sauce 500g", "brand": "Heinz",
             "category": "Pantry", "subcategory": "Tomato Sauce",
             "aliases": ["ketchup"], "in_stock": True, "popularity_score": 80},
        ])
        await db.products.create_index(
            [("name", TEXT), ("aliases", TEXT), ("category", TEXT), ("subcategory", TEXT)],
            name="product_text_search",
        )

        # "potato" is not in any alias — must go through the $text fallback.
        hits = await resolution.search_products(db, "potato")
        brands = [h["brand"] for h in hits]
        assert set(brands) == {"Smith's", "Nobby's"}, f"expected the two potato products, got {brands}"
        assert brands[0] == "Smith's", f"in-stock product must rank first, got {brands}"
        assert brands[-1] == "Nobby's", f"out-of-stock product must rank last, got {brands}"
        print(f"  '$text' path   -> {brands} (in-stock first)")

        # Sauce should not bleed in — confirms the index isn't matching everything.
        sauce = await resolution.search_products(db, "tomato")
        assert [h["brand"] for h in sauce] == ["Heinz"], f"unexpected: {sauce}"
        print(f"  '$text' tomato -> Heinz")
    finally:
        await client.drop_database(db_name)
        client.close()


def main() -> None:
    uri = os.environ.get("MONGODB_URI")
    if not uri:
        print("  SKIPPED: MONGODB_URI not set (integration test requires real MongoDB)")
        return
    try:
        asyncio.run(run(uri))
    except Exception as exc:
        print(f"  FAILED: {type(exc).__name__}: {exc}")
        sys.exit(1)
    print("\nALL RESOLUTION INTEGRATION CHECKS PASSED")


if __name__ == "__main__":
    main()
