"""
Item resolution orchestrator.

Runs the full brand-resolution decision tree so the Vapi agent calls ONE
tool, not three. Conversation flow is the agent's job; this deterministic
business logic is Python's job.

Given a raw mention from the call ("chips", "Smith's chips") and the customer,
resolve_item() returns a single instruction telling the agent what to do next.

Decision tree:
  1. Identify the subcategory via product search. None -> ASK.
  2. Resolve the brand:
     a. Brand named in the mention and stocked      -> RESOLVED
     b. Customer bought this subcategory before     -> CONFIRM (history)
     c. A popular brand exists for the subcategory  -> RECOMMEND (popularity)
     d. Nothing to go on                            -> ASK
"""

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.services import customer_history, resolution

# resolution statuses returned to the agent
RESOLVED = "resolved"  # exact product locked in
CONFIRM = "confirm"  # propose a product, agent must confirm
RECOMMEND = "recommend"  # suggest a brand, agent must confirm
ASK = "ask"  # nothing to go on, agent must ask


def _strip_brands(mention: str, known_brands: set[str]) -> tuple[str, str | None]:
    """Separate a brand name from the rest of the mention.

    "Doritos chips" -> ("chips", "Doritos"). Searching on the product term
    alone ("chips") is far more reliable than searching the whole phrase.
    Returns (remaining_text, matched_brand_or_None).
    """
    text = mention.lower()
    for brand in known_brands:
        bl = brand.lower()
        if bl in text:
            remaining = text.replace(bl, " ").strip()
            return (remaining or mention, brand)
    return (mention, None)


async def resolve_item(
    db: AsyncIOMotorDatabase,
    mention: str,
    customer_id: str,
) -> dict:
    """Resolve one spoken item to an instruction for the agent.

    Returns a dict with:
        status   — one of RESOLVED / CONFIRM / RECOMMEND / ASK
        mention  — the original spoken text
        message  — a short natural-language instruction for the agent
        plus status-specific fields (product, subcategory, source...).
    """
    mention = (mention or "").strip()
    if not mention:
        return {
            "status": ASK,
            "mention": mention,
            "message": "I didn't catch that — could you say it again?",
        }

    # --- detect a brand in the mention, search on the product term only ---
    known_brands = set(await db.products.distinct("brand"))
    search_term, named_brand = _strip_brands(mention, known_brands)

    # --- Stage 1: identify the subcategory via product search ---
    candidates = await resolution.search_products(db, search_term, limit=10)
    if not candidates:
        return {
            "status": ASK,
            "mention": mention,
            "message": f"I couldn't find '{mention}' — could you describe it differently?",
        }

    subcategory = candidates[0]["subcategory"]

    # --- Stage 2a: brand named in the mention and stocked in this subcategory? ---
    if named_brand is not None:
        for product in candidates:
            if product["brand"] == named_brand:
                return {
                    "status": RESOLVED,
                    "mention": mention,
                    "subcategory": subcategory,
                    "brand_source": "mentioned",
                    "product": product,
                    "message": f"Got it — {product['name']}.",
                }
        # brand named but not available here — note it, continue to fallback

    # --- Stage 2b: history-first — did they buy this subcategory before? ---
    past = await customer_history.infer_brand_from_history(db, customer_id, subcategory)
    if past is not None:
        return {
            "status": CONFIRM,
            "mention": mention,
            "subcategory": subcategory,
            "brand_source": "history",
            "product": past,
            "message": (
                f"You ordered {past['name']} last time — would you like that again?"
            ),
        }

    # --- Stage 2c: popularity fallback — recommend the top brand ---
    top_brand = await resolution.get_top_brand(db, subcategory)
    if top_brand is not None:
        return {
            "status": RECOMMEND,
            "mention": mention,
            "subcategory": subcategory,
            "brand_source": "recommended",
            "brand": top_brand["brand"],
            "message": (
                f"Our most popular {subcategory.lower()} is "
                f"{top_brand['brand']} — would you like that?"
            ),
        }

    # --- Stage 2d: nothing to go on — ask ---
    return {
        "status": ASK,
        "mention": mention,
        "subcategory": subcategory,
        "message": f"Which brand of {subcategory.lower()} would you like?",
    }


async def resolve_brand(
    db: AsyncIOMotorDatabase,
    subcategory: str,
    brand: str,
) -> dict:
    """Resolve a customer-named brand within a subcategory to a product.

    Called after resolve_item returned 'recommend' or 'ask' and the customer
    then named a brand. Picks that brand's best product in the subcategory
    (in-stock first, then popularity — search_products already ranks this way).

    Returns a dict with status RESOLVED (product found) or ASK (brand not
    stocked in this subcategory).
    """
    brand = (brand or "").strip()
    candidates = await resolution.search_products(db, subcategory, limit=50)
    for product in candidates:
        if product["brand"].lower() == brand.lower():
            return {
                "status": RESOLVED,
                "subcategory": subcategory,
                "brand_source": "mentioned",
                "product": product,
                "message": f"Got it — {product['name']}.",
            }
    return {
        "status": ASK,
        "subcategory": subcategory,
        "message": (
            f"Sorry, we don't have {brand} in {subcategory.lower()} — "
            f"is there another brand you'd like?"
        ),
    }
