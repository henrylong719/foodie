"""
Customer history service.

Looks up what a customer bought before — the data behind history-first brand
resolution. When a customer says "chips" with no brand, the agent checks here:
if they ordered Smith's chips last time, the agent confirms that rather than
recommending a brand from scratch.

Lookups filter by SUBCATEGORY ("Potato Chips"), not category ("Snacks"), so
"what chips did they buy" returns chips — not all snacks.

Kept HTTP-free so it can be unit-tested directly.
"""

from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase


def _to_object_id(value: str) -> ObjectId | None:
    """Parse a string into an ObjectId, or None if it isn't a valid id."""
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        return None


async def get_history(
    db: AsyncIOMotorDatabase,
    customer_id: str,
    subcategory: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """Return a customer's past order items, most recent first.

    Args:
        db: the database handle.
        customer_id: the customer's _id as a string.
        subcategory: if given, only items in this subcategory are returned —
            this is the brand-inference query ("what chips did they buy?").
        limit: max items to return.

    Returns:
        A list of past-purchase items, each:
            { product_id, name, category, subcategory, quantity, ordered_at }
        Most recent first. Empty if the customer or matching items don't exist.
    """
    oid = _to_object_id(customer_id)
    if oid is None:
        return []

    orders = (
        await db.order_history.find({"customer_id": oid})
        .sort("date", -1)
        .to_list(length=200)
    )

    items: list[dict] = []
    for order in orders:
        for item in order.get("items", []):
            if subcategory and item.get("subcategory") != subcategory:
                continue
            items.append(
                {
                    "product_id": str(item["product_id"]),
                    "name": item["name"],
                    "category": item["category"],
                    "subcategory": item["subcategory"],
                    "quantity": item["quantity"],
                    "ordered_at": order["date"],
                }
            )
            if len(items) >= limit:
                return items
    return items


async def infer_brand_from_history(
    db: AsyncIOMotorDatabase,
    customer_id: str,
    subcategory: str,
) -> dict | None:
    """Find the most recent product a customer bought in a subcategory.

    This is the history-first step of brand resolution. If it returns a
    product, the agent can confirm it directly:
        "You ordered Smith's chips last time — same again?"
    Returns None if the customer has no history in that subcategory, in which
    case the caller falls back to brand-popularity recommendation.
    """
    items = await get_history(db, customer_id, subcategory=subcategory, limit=1)
    return items[0] if items else None
