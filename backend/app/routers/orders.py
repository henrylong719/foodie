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
    """Fetch one captured order by id, with customer name joined."""
    order = await orders.get_order(db, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order
