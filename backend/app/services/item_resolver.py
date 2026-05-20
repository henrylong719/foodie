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
import re

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.services import customer_history, resolution

# resolution statuses returned to the agent
RESOLVED = "resolved"      # exact product locked in
CONFIRM = "confirm"        # propose a product, agent must confirm
RECOMMEND = "recommend"    # suggest a brand, agent must confirm
ASK = "ask"                # nothing to go on, agent must ask

COMMON_BRAND_ALIASES = {
    "Coca-Cola": {"coca cola", "coca-cola"},
    "Red Bull": {"redbull"},
}


def _normalize_phrase(value: str) -> str:
    """Normalize spoken text for brand matching."""
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.lower()).split())


def _brand_aliases(brand: str) -> set[str]:
    normalized = _normalize_phrase(brand)
    aliases = {normalized, normalized.replace(" ", "")}
    aliases.update(_normalize_phrase(alias)
                   for alias in COMMON_BRAND_ALIASES.get(brand, set()))
    aliases.update(_normalize_phrase(alias).replace(" ", "")
                   for alias in COMMON_BRAND_ALIASES.get(brand, set()))
    return {alias for alias in aliases if alias}


def _contains_phrase(text: str, phrase: str) -> bool:
    return f" {phrase} " in f" {text} "


def _remove_phrase(text: str, phrase: str) -> str:
    pattern = rf"(^| ){re.escape(phrase)}(?= |$)"
    return " ".join(re.sub(pattern, " ", text).split())


def _natural_item_name(brand: str, subcategory: str) -> str:
    """Short spoken label for a recommended brand/item pair."""
    return f"{brand} {subcategory.lower()}"


def _resolve_brand_name(brand: str, known_brands: set[str]) -> str | None:
    """Return the stocked brand matching a spoken brand variant."""
    normalized = _normalize_phrase(brand)
    if not normalized:
        return None

    for known_brand in sorted(known_brands, key=len, reverse=True):
        if normalized in _brand_aliases(known_brand):
            return known_brand
    return None


def _strip_brands(mention: str, known_brands: set[str]) -> tuple[str, str | None]:
    """Separate a brand name from the rest of the mention.

    "Doritos chips" -> ("chips", "Doritos"). Searching on the product term
    alone ("chips") is far more reliable than searching the whole phrase.
    Returns (remaining_text, matched_brand_or_None).
    """
    text = _normalize_phrase(mention)
    for brand in sorted(known_brands, key=len, reverse=True):
        aliases = sorted(_brand_aliases(brand), key=len, reverse=True)
        for alias in aliases:
            if _contains_phrase(text, alias):
                remaining = _remove_phrase(text, alias)
                return (remaining or mention, brand)
    return (mention, None)


async def _brand_options(
    db: AsyncIOMotorDatabase,
    subcategory: str,
    limit: int = 3,
) -> list[str]:
    """Return a short, ranked brand list the agent can offer if asked."""
    options: list[str] = []
    seen: set[str] = set()

    for row in await resolution.get_top_brands(db, subcategory, limit=limit):
        brand = row["brand"]
        if brand not in seen:
            seen.add(brand)
            options.append(brand)

    for brand in await resolution.list_available_brands(db, subcategory, limit=limit):
        if brand not in seen:
            seen.add(brand)
            options.append(brand)
        if len(options) >= limit:
            break

    return options[:limit]


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
        return {"status": ASK, "mention": mention,
                "message": "I didn't catch that — could you say it again?"}

    # --- detect a brand in the mention, search on the product term only ---
    known_brands = set(await db.products.distinct("brand"))
    search_term, named_brand = _strip_brands(mention, known_brands)

    # --- Stage 1: identify the subcategory via product search ---
    candidates = await resolution.search_products(db, search_term, limit=10)
    if not candidates and named_brand is not None:
        candidates = await resolution.search_products(db, mention, limit=10)
    if not candidates:
        return {"status": ASK, "mention": mention,
                "message": f"I couldn't find '{mention}' — could you describe it differently?"}

    subcategory = candidates[0]["subcategory"]

    # --- Stage 2a: brand named in the mention and stocked in this subcategory? ---
    if named_brand is not None:
        for product in candidates:
            if product["brand"] == named_brand:
                return {
                    "status": RESOLVED, "mention": mention,
                    "subcategory": subcategory, "brand_source": "mentioned",
                    "product": product,
                    "message": f"Got it — {product['name']}.",
                }
        # brand named but not available here — note it, continue to fallback

    # --- Stage 2b: history-first — did they buy this subcategory before? ---
    past = await customer_history.infer_brand_from_history(
        db, customer_id, subcategory)
    if past is not None:
        return {
            "status": CONFIRM, "mention": mention,
            "subcategory": subcategory, "brand_source": "history",
            "product": past,
            "message": (f"You ordered {past['name']} last time — "
                        f"would you like that again?"),
        }

    # --- Stage 2c: popularity fallback — recommend the top brand ---
    brand_options = await _brand_options(db, subcategory)
    top_brand = await resolution.get_top_brand(db, subcategory)
    if top_brand is not None:
        recommended_product = next(
            (product for product in candidates if product["brand"] == top_brand["brand"]),
            None,
        )
        if recommended_product is not None:
            recommended_product = {
                **recommended_product,
                "name": _natural_item_name(top_brand["brand"], subcategory),
            }
        return {
            "status": RECOMMEND, "mention": mention,
            "subcategory": subcategory, "brand_source": "recommended",
            "brand": top_brand["brand"], "available_brands": brand_options,
            "product": recommended_product,
            "message": (f"Our most popular {subcategory.lower()} is "
                        f"{top_brand['brand']} — would you like that?"),
        }

    # --- Stage 2d: nothing to go on — ask ---
    return {
        "status": ASK, "mention": mention, "subcategory": subcategory,
        "available_brands": brand_options,
        "next_tool": "resolve_brand",
        "next_tool_instruction": (
            "When the customer names a brand for this item, call resolve_brand "
            "with this subcategory and the customer's brand before asking quantity."
        ),
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
    candidates = await resolution.search_products(db, subcategory, limit=50)
    known_brands = {
        product["brand"]
        for product in candidates
        if isinstance(product.get("brand"), str)
    }
    resolved_brand = _resolve_brand_name(brand or "", known_brands)

    for product in candidates:
        if product["brand"] == resolved_brand:
            return {
                "status": RESOLVED, "subcategory": subcategory,
                "brand_source": "mentioned", "product": product,
                "message": f"Got it — {product['name']}.",
            }
    brand_options = await _brand_options(db, subcategory)
    return {
        "status": ASK, "subcategory": subcategory,
        "available_brands": brand_options,
        "message": (f"Sorry, we don't have {brand} in {subcategory.lower()} — "
                    f"is there another brand you'd like?"),
    }
