"""
Product resolution service.

Turns a free-text mention from a phone call ("chips", "tomato sauce") into a
ranked list of real catalog products. This is the logic behind the
search_products tool the Vapi agent calls.

Strategy (in order):
  1. Exact alias match  — the mention appears verbatim in a product's aliases.
  2. Text search        — MongoDB text index over name / aliases / category.
Results are ranked by in-stock first, then popularity_score.

Kept HTTP-free so it can be unit-tested directly.
"""
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase


def _serialize(doc: dict[str, Any]) -> dict[str, Any]:
    """Convert a Mongo product document to a JSON-safe dict."""
    doc = dict(doc)
    doc["_id"] = str(doc["_id"])
    doc.pop("score", None)  # internal text-search score, not for the client
    return doc


def _rank(products: list[dict]) -> list[dict]:
    """In-stock products first, then higher popularity_score first."""
    return sorted(
        products,
        key=lambda p: (not p.get("in_stock", False), -p.get("popularity_score", 0)),
    )


async def search_products(
    db: AsyncIOMotorDatabase,
    query: str,
    limit: int = 5,
) -> list[dict]:
    """Resolve a free-text mention to ranked candidate products.

    Args:
        db: the database handle.
        query: what the customer said, e.g. "chips".
        limit: max products to return.

    Returns:
        A ranked list of JSON-safe product dicts (may be empty).
    """
    normalized = query.strip().lower()
    if not normalized:
        return []

    # 1. Exact alias match — most reliable signal.
    alias_hits = await db.products.find(
        {"aliases": normalized}
    ).to_list(length=100)

    if alias_hits:
        return [_serialize(p) for p in _rank(alias_hits)[:limit]]

    # 2. Fall back to the text index over name / aliases / category.
    try:
        text_hits = await db.products.find(
            {"$text": {"$search": normalized}},
            {"score": {"$meta": "textScore"}},
        ).to_list(length=100)
    except Exception:
        # Text index unavailable (e.g. not yet built) — degrade to no match
        # rather than crashing the call. The caller treats [] as "ask".
        text_hits = []

    return [_serialize(p) for p in _rank(text_hits)[:limit]]


async def get_top_brand(
    db: AsyncIOMotorDatabase,
    subcategory: str,
) -> dict | None:
    """Return the most popular brand for a subcategory, or None.

    Queries the brand_popularity collection. This is the no-brand,
    no-history fallback: "our most popular chips is Smith's".
    Returns None if the subcategory has no brand-popularity data, in which
    case the caller asks the customer rather than guessing.
    """
    doc = await db.brand_popularity.find_one(
        {"subcategory": subcategory},
        sort=[("score", -1)],
    )
    if doc is None:
        return None
    return {
        "brand": doc["brand"],
        "subcategory": doc["subcategory"],
        "score": doc["score"],
    }
