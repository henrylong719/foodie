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


class ProductListResult(SearchResult):
    in_stock_count: int


@router.get("", response_model=ProductListResult)
async def list_products(
    category: str | None = Query(None, description="Filter by category"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Browse the catalog, optionally filtered by category."""
    query = {"category": category} if category else {}
    total = await db.products.count_documents(query)
    in_stock_count = await db.products.count_documents({**query, "in_stock": True})
    docs = await db.products.find(query).sort(
        "popularity_score", -1).to_list(length=limit)
    products = []
    for p in docs:
        p["_id"] = str(p["_id"])
        products.append(p)
    return ProductListResult(
        query=category or "all",
        count=total,
        in_stock_count=in_stock_count,
        products=products,
    )


@router.get("/categories")
async def list_categories(db: AsyncIOMotorDatabase = Depends(get_db)):
    """Distinct category names — for the catalog filter."""
    cats = await db.products.distinct("category")
    return {"categories": sorted(cats)}


@router.get("/search", response_model=SearchResult)
async def search_products(
    q: str = Query(..., min_length=1, description="What the customer said, e.g. 'chips'"),
    limit: int = Query(5, ge=1, le=20, description="Max products to return"),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Resolve a free-text product mention to ranked catalog products.

    Tries exact alias match first, then a text-index search. Results are
    ranked in-stock first, then by popularity.
    """
    products = await resolution.search_products(db, q, limit)
    return SearchResult(query=q, count=len(products), products=products)
