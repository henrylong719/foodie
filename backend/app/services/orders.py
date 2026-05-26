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
        transcript_url: ignored. Transcripts are stored on the call record.

    Returns:
        { ok: True, order_id } on success, or { ok: False, error } if the
        input is invalid (no customer, no items).
    """
    oid = _to_object_id(customer_id)
    if oid is None:
        return {"ok": False, "error": "invalid customer_id"}
    if not items:
        return {"ok": False, "error": "order has no items"}

    # Idempotency: tool-calling LLMs occasionally re-invoke save_order on retry
    # for the same call. Return the existing order rather than creating a second
    # row (which would double-bill / double-fulfil). The unique index on call_id
    # (see seed.create_indexes) is the race-safe backstop.
    if call_id:
        existing = await db.captured_orders.find_one({"call_id": call_id})
        if existing is not None:
            return {"ok": True, "order_id": str(existing["_id"])}

    # Validate quantity and product_id per item. Reject the whole order if any
    # item is malformed — fulfilment downstream trusts these rows.
    parsed: list[tuple[ObjectId, dict]] = []
    for item in items:
        qty_raw = item.get("quantity", 1)
        # bool is a subclass of int — reject it explicitly so True/False aren't
        # silently treated as quantity 1/0.
        if isinstance(qty_raw, bool):
            return {"ok": False, "error": f"invalid quantity: {qty_raw!r}"}
        try:
            quantity = int(qty_raw)
        except (TypeError, ValueError):
            return {"ok": False, "error": f"invalid quantity: {qty_raw!r}"}
        if quantity <= 0:
            return {"ok": False, "error": f"quantity must be positive, got {quantity}"}

        pid_raw = item.get("product_id", "")
        pid = _to_object_id(str(pid_raw))
        if pid is None:
            return {"ok": False, "error": f"invalid product_id: {pid_raw!r}"}

        parsed.append((pid, {
            "product_id": str(pid),
            "name": item.get("name", ""),
            "quantity": quantity,
            "brand_source": item.get("brand_source", "mentioned"),
        }))

    # One round-trip to confirm every referenced product exists.
    pids = list({pid for pid, _ in parsed})
    found = await db.products.find(
        {"_id": {"$in": pids}}, {"_id": 1}
    ).to_list(length=len(pids))
    found_ids = {f["_id"] for f in found}
    missing = [str(pid) for pid in pids if pid not in found_ids]
    if missing:
        return {"ok": False, "error": f"unknown product_id(s): {', '.join(missing)}"}

    # Dedupe by product_id with last-write-wins. If the LLM emits both the
    # original and corrected line for one product (Script 9 recap correction
    # where the customer changes quantity mid-recap), the latest entry should
    # win rather than producing two rows for one item.
    deduped: dict[str, dict] = {}
    for _, clean in parsed:
        deduped[clean["product_id"]] = clean
    clean_items = list(deduped.values())

    doc = {
        "customer_id": oid,
        "call_id": call_id,
        "created_at": datetime.now(timezone.utc),
        "status": "pending_fulfillment",
        "items": clean_items,
        "transcript_url": None,
    }
    result = await db.captured_orders.insert_one(doc)
    return {"ok": True, "order_id": str(result.inserted_id)}


async def get_order(
    db: AsyncIOMotorDatabase,
    order_id: str,
) -> dict | None:
    """Return one captured order with customer name and item count joined.

    Returns None for invalid ids or missing rows so the router can raise 404.
    """
    oid = _to_object_id(order_id)
    if oid is None:
        return None

    o = await db.captured_orders.find_one({"_id": oid})
    if o is None:
        return None

    customer = await db.customers.find_one({"_id": o["customer_id"]})
    return {
        "_id": str(o["_id"]),
        "customer_id": str(o["customer_id"]),
        "customer_name": customer["name"] if customer else "Unknown",
        "call_id": o.get("call_id", ""),
        "created_at": o["created_at"].isoformat() if o.get("created_at") else None,
        "status": o.get("status", ""),
        "items": o.get("items", []),
        "item_count": len(o.get("items", [])),
        "transcript_url": o.get("transcript_url"),
    }


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
