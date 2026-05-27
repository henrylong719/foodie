"""
Demo-only operations. Gated by the DEMO_MODE setting.

Lets the dashboard reset transient demo state (captured orders, the demo
customer's do-not-call flag) between takes without re-running the seed
script. Catalog, customers, order history are left intact.
"""

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import settings
from app.db import get_db

router = APIRouter(prefix="/demo", tags=["demo"])

# The pinned demo customer from seed.py. Reset un-flags their do_not_call
# so the opt-out branch can be re-demoed without reseeding the catalog.
DEMO_CUSTOMER_PHONE = "+12176373205"


def _require_demo_mode() -> None:
    if not settings.demo_mode:
        raise HTTPException(
            status_code=403,
            detail="Demo mode disabled. Set DEMO_MODE=true to enable.",
        )


@router.post("/reset")
async def reset_demo(db: AsyncIOMotorDatabase = Depends(get_db)):
    """Clean transient demo state. Idempotent.

    Drops every captured order, clears live call records, and un-flags
    do-not-call on the seeded demo customer. The catalog, customer list,
    and order history are untouched so brand inference still works.
    """
    _require_demo_mode()

    orders_deleted = (await db.captured_orders.delete_many({})).deleted_count
    calls_deleted = (await db.calls.delete_many({})).deleted_count
    customer_update = await db.customers.update_one(
        {"phone": DEMO_CUSTOMER_PHONE},
        {"$set": {"do_not_call": False}},
    )

    return {
        "ok": True,
        "captured_orders_deleted": orders_deleted,
        "calls_deleted": calls_deleted,
        "demo_customer_reset": customer_update.modified_count == 1,
    }
