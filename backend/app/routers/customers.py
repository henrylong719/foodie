"""Customer endpoints. get_customer_history powers history-first brand inference."""
from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from app.db import get_db
from app.services import customer_history

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("")
async def list_customers(
    limit: int = Query(100, ge=1, le=500),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """List customers — used by the dashboard to pick who to call."""
    docs = await db.customers.find().sort("name", 1).to_list(length=limit)
    customers = []
    for c in docs:
        customers.append({
            "_id": str(c["_id"]),
            "name": c["name"],
            "phone": c["phone"],
            "do_not_call": c.get("do_not_call", False),
            "preferred_language": c.get("preferred_language", "en"),
        })
    return {"count": len(customers), "customers": customers}


class HistoryResponse(BaseModel):
    customer_id: str
    subcategory: str | None
    count: int
    items: list[dict]


@router.get("/{customer_id}/history", response_model=HistoryResponse)
async def get_customer_history(
    customer_id: str,
    subcategory: str | None = Query(
        None, description="Filter to one subcategory, e.g. 'Potato Chips'"),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Return a customer's past purchases, most recent first.

    With `subcategory`, this is the history-first brand-inference lookup:
    the most recent item tells the agent which brand to confirm.
    """
    # 404 only if the customer truly does not exist; an existing customer
    # with no matching history is a valid empty result, not an error.
    from app.services.customer_history import _to_object_id
    oid = _to_object_id(customer_id)
    if oid is None or await db.customers.count_documents({"_id": oid}) == 0:
        raise HTTPException(status_code=404, detail="Customer not found")

    items = await customer_history.get_history(
        db, customer_id, subcategory=subcategory, limit=limit)
    return HistoryResponse(
        customer_id=customer_id,
        subcategory=subcategory,
        count=len(items),
        items=items,
    )
