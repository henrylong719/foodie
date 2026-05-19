"""Order endpoints — review captured orders in the dashboard."""
from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db import get_db
from app.services import orders

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("")
async def list_orders(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """List captured orders, most recent first, with customer names."""
    items = await orders.list_orders(db, limit)
    return {"count": len(items), "orders": items}


@router.get("/{order_id}")
async def get_order(
    order_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Fetch one captured order by id."""
    from bson import ObjectId
    from bson.errors import InvalidId
    try:
        oid = ObjectId(order_id)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=404, detail="Order not found")

    doc = await db.captured_orders.find_one({"_id": oid})
    if doc is None:
        raise HTTPException(status_code=404, detail="Order not found")

    doc["_id"] = str(doc["_id"])
    doc["customer_id"] = str(doc["customer_id"])
    if doc.get("created_at"):
        doc["created_at"] = doc["created_at"].isoformat()
    return doc
