"""Product endpoints. search_products is the tool the Vapi agent calls."""

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from app.db import get_db
from app.services import resolution

router = APIRouter(prefix="/products", tags=["products"])


class SearchResult(BaseModel):
    query: str
    count: int
    products: list[dict]


@router.get("/search", response_model=SearchResult)
async def search_products(
    q: str = Query(
        ..., min_length=1, description="What the customer said, e.g. 'chips'"
    ),
    limit: int = Query(5, ge=1, le=20, description="Max products to return"),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Resolve a free-text product mention to ranked catalog products.

    Tries exact alias match first, then a text-index search. Results are
    ranked in-stock first, then by popularity.
    """
    products = await resolution.search_products(db, q, limit)
    return SearchResult(query=q, count=len(products), products=products)
