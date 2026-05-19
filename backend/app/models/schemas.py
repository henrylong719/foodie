"""
Pydantic schemas mirroring the MongoDB collections.

These document the data shapes and validate API input/output. ObjectId fields
are represented as strings at the API boundary.
"""
from datetime import datetime

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------
# Products
# --------------------------------------------------------------------------
class Product(BaseModel):
    id: str = Field(alias="_id")
    name: str
    brand: str
    category: str
    subcategory: str
    aliases: list[str]
    size: str
    unit: str
    price: float
    in_stock: bool
    popularity_score: int

    model_config = {"populate_by_name": True}


# --------------------------------------------------------------------------
# Customers
# --------------------------------------------------------------------------
class Consent(BaseModel):
    given: bool
    date: datetime
    method: str


class Customer(BaseModel):
    id: str = Field(alias="_id")
    name: str
    phone: str
    do_not_call: bool
    consent: Consent
    preferred_language: str

    model_config = {"populate_by_name": True}


# --------------------------------------------------------------------------
# Order history
# --------------------------------------------------------------------------
class HistoryItem(BaseModel):
    product_id: str
    name: str
    category: str
    subcategory: str
    quantity: int


class OrderHistory(BaseModel):
    id: str = Field(alias="_id")
    customer_id: str
    date: datetime
    items: list[HistoryItem]

    model_config = {"populate_by_name": True}


# --------------------------------------------------------------------------
# Captured orders — produced by a completed call
# --------------------------------------------------------------------------
class CapturedItem(BaseModel):
    product_id: str
    name: str
    quantity: int
    brand_source: str  # history | mentioned | recommended


class CapturedOrder(BaseModel):
    id: str = Field(alias="_id")
    customer_id: str
    call_id: str
    created_at: datetime
    status: str
    items: list[CapturedItem]
    transcript_url: str | None = None

    model_config = {"populate_by_name": True}
