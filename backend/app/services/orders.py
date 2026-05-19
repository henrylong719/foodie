"""
Order service.

Persists a confirmed order as a captured_orders document — the deliverable
of a completed call. Also handles do-not-call opt-outs.

Kept HTTP-free so it can be unit-tested directly.
"""
from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase


def _to_object_id(value: str) -> ObjectId | None:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        return None


async def save_order(
    db: AsyncIOMotorDatabase,
    customer_id: str,
    call_id: str,
    items: list[dict],
    transcript_url: str | None = None,
) -> dict:
    """Persist a confirmed order.

    Args:
        db: database handle.
        customer_id: the customer's _id as a string.
        call_id: the Vapi call id.
        items: confirmed items, each with product_id, name, quantity,
            brand_source.
        transcript_url: optional link to the call transcript.

    Returns:
        { ok: True, order_id } on success, or { ok: False, error } if the
        input is invalid (no customer, no items).
    """
    oid = _to_object_id(customer_id)
    if oid is None:
        return {"ok": False, "error": "invalid customer_id"}
    if not items:
        return {"ok": False, "error": "order has no items"}

    # normalize items — keep only the fields the schema defines
    clean_items = []
    for item in items:
        clean_items.append({
            "product_id": str(item.get("product_id", "")),
            "name": item.get("name", ""),
            "quantity": int(item.get("quantity", 1)),
            "brand_source": item.get("brand_source", "mentioned"),
        })

    doc = {
        "customer_id": oid,
        "call_id": call_id,
        "created_at": datetime.now(timezone.utc),
        "status": "pending_fulfilment",
        "items": clean_items,
        "transcript_url": transcript_url,
    }
    result = await db.captured_orders.insert_one(doc)
    return {"ok": True, "order_id": str(result.inserted_id)}


async def list_orders(
    db: AsyncIOMotorDatabase,
    limit: int = 50,
) -> list[dict]:
    """Return captured orders, most recent first, with customer names joined."""
    orders_raw = await db.captured_orders.find().sort(
        "created_at", -1).to_list(length=limit)

    # join customer names in one query
    cust_ids = list({o["customer_id"] for o in orders_raw})
    customers = await db.customers.find(
        {"_id": {"$in": cust_ids}}).to_list(length=len(cust_ids) or 1)
    names = {c["_id"]: c["name"] for c in customers}

    result = []
    for o in orders_raw:
        result.append({
            "_id": str(o["_id"]),
            "customer_id": str(o["customer_id"]),
            "customer_name": names.get(o["customer_id"], "Unknown"),
            "call_id": o.get("call_id", ""),
            "created_at": o["created_at"].isoformat() if o.get("created_at") else None,
            "status": o.get("status", ""),
            "items": o.get("items", []),
            "item_count": len(o.get("items", [])),
            "transcript_url": o.get("transcript_url"),
        })
    return result


async def flag_do_not_call(
    db: AsyncIOMotorDatabase,
    customer_id: str,
) -> dict:
    """Record a customer's opt-out by setting their do_not_call flag.

    Returns { ok: True } if a customer was updated, else { ok: False }.
    """
    oid = _to_object_id(customer_id)
    if oid is None:
        return {"ok": False, "error": "invalid customer_id"}

    result = await db.customers.update_one(
        {"_id": oid}, {"$set": {"do_not_call": True}}
    )
    if result.matched_count == 0:
        return {"ok": False, "error": "customer not found"}
    return {"ok": True}
