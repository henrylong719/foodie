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
RESOLVED = "resolved"  # exact product locked in
CONFIRM = "confirm"  # propose a product, agent must confirm
RECOMMEND = "recommend"  # suggest a brand, agent must confirm
ASK = "ask"  # nothing to go on, agent must ask


def _normalize_phrase(value: str) -> str:
    """Normalize spoken text for brand matching."""
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.lower()).split())


def _brand_aliases(
    brand: str,
    configured_aliases: set[str] | None = None,
) -> set[str]:
    normalized = _normalize_phrase(brand)
    aliases = {normalized, normalized.replace(" ", "")}
    for alias in configured_aliases or set():
        normalized_alias = _normalize_phrase(alias)
        aliases.add(normalized_alias)
        aliases.add(normalized_alias.replace(" ", ""))
    return {alias for alias in aliases if alias}


def _brand_alias_map(products: list[dict]) -> dict[str, set[str]]:
    aliases_by_brand: dict[str, set[str]] = {}
    for product in products:
        brand = product.get("brand")
        if not isinstance(brand, str):
            continue

        aliases = aliases_by_brand.setdefault(brand, set())
        for alias in product.get("brand_aliases") or []:
            if isinstance(alias, str):
                aliases.add(alias)
    return aliases_by_brand


async def _catalog_brand_alias_map(
    db: AsyncIOMotorDatabase,
) -> dict[str, set[str]]:
    products = await db.products.find(
        {},
        {"brand": 1, "brand_aliases": 1},
    ).to_list(length=10000)
    return _brand_alias_map(products)


def _contains_phrase(text: str, phrase: str) -> bool:
    return f" {phrase} " in f" {text} "


def _remove_phrase(text: str, phrase: str) -> str:
    pattern = rf"(^| ){re.escape(phrase)}(?= |$)"
    return " ".join(re.sub(pattern, " ", text).split())


def _natural_item_name(brand: str, subcategory: str) -> str:
    """Short spoken label for a recommended brand/item pair."""
    return f"{brand} {subcategory.lower()}"


def _serialize_product(product: dict) -> dict:
    product = dict(product)
    product["_id"] = str(product["_id"])
    product.pop("score", None)
    return product


def _format_brand_options(brands: list[str]) -> str:
    if len(brands) <= 1:
        return "".join(brands)
    return f"{', '.join(brands[:-1])}, or {brands[-1]}"


def _resolve_brand_name(
    brand: str,
    aliases_by_brand: dict[str, set[str]],
) -> str | None:
    """Return the stocked brand matching a spoken brand variant."""
    normalized = _normalize_phrase(brand)
    if not normalized:
        return None

    for known_brand in sorted(aliases_by_brand, key=len, reverse=True):
        if normalized in _brand_aliases(
            known_brand,
            aliases_by_brand[known_brand],
        ):
            return known_brand
    return None


def _strip_brands(
    mention: str,
    aliases_by_brand: dict[str, set[str]],
) -> tuple[str, str | None]:
    """Separate a brand name from the rest of the mention.

    "Doritos chips" -> ("chips", "Doritos"). Searching on the product term
    alone ("chips") is far more reliable than searching the whole phrase.
    Returns (remaining_text, matched_brand_or_None). When the mention is
    only a brand ("Doritos"), remaining is "" — the caller is expected to
    pivot to that brand's subcategory rather than search for the brand name.
    """
    text = _normalize_phrase(mention)
    for brand in sorted(aliases_by_brand, key=len, reverse=True):
        aliases = sorted(
            _brand_aliases(brand, aliases_by_brand[brand]),
            key=len,
            reverse=True,
        )
        for alias in aliases:
            if _contains_phrase(text, alias):
                remaining = _remove_phrase(text, alias)
                return (remaining, brand)
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
        return {
            "status": ASK,
            "mention": mention,
            "message": "I didn't catch that — could you say it again?",
        }

    # --- detect a brand in the mention, search on the product term only ---
    aliases_by_brand = await _catalog_brand_alias_map(db)
    search_term, named_brand = _strip_brands(mention, aliases_by_brand)

    # Brand-only mention ("Doritos"): the brand name alone isn't a product
    # alias, so pivot to that brand's subcategory before searching.
    if not search_term and named_brand is not None:
        branded = await db.products.find_one(
            {"brand": named_brand},
            sort=[("popularity_score", -1)],
        )
        if branded is not None:
            search_term = branded["subcategory"]

    # --- Stage 1: identify the subcategory via product search ---
    candidates = await resolution.search_products(db, search_term, limit=10)
    if not candidates and named_brand is not None:
        candidates = await resolution.search_products(db, mention, limit=10)
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
            # Must be in-stock: candidates are ranked in-stock-first, but if
            # every product for this brand is OOS the loop would otherwise
            # confirm a SKU we can't actually fulfil.
            if product["brand"] == named_brand and product.get("in_stock", False):
                return {
                    "status": RESOLVED,
                    "mention": mention,
                    "subcategory": subcategory,
                    "brand_source": "mentioned",
                    "product": product,
                    "message": (
                        f"Got it — {_natural_item_name(product['brand'], subcategory)}."
                    ),
                }
        # brand named but not available (or all OOS) — continue to fallback

    # --- Stage 2b: history-first — did they buy this subcategory before? ---
    past = await customer_history.infer_brand_from_history(db, customer_id, subcategory)
    if past is not None:
        brand_options = await _brand_options(db, subcategory)
        return {
            "status": CONFIRM,
            "mention": mention,
            "subcategory": subcategory,
            "brand_source": "history",
            "product": past,
            "available_brands": brand_options,
            "next_tool": "resolve_brand",
            "next_tool_instruction": (
                "If the customer asks for something else or names another "
                "brand, ask which brand they would like and call resolve_brand "
                "with this subcategory and that brand before asking quantity."
            ),
            "message": (
                f"For {subcategory.lower()}, would you like your usual {past['name']}?"
            ),
        }

    # --- Stage 2c: popularity fallback — recommend the top brand ---
    # Walk popularity in rank order and stop at the first brand with an
    # in-stock candidate, so we don't recommend a brand that's fully OOS.
    brand_options = await _brand_options(db, subcategory)
    for top in await resolution.get_top_brands(db, subcategory):
        recommended_product = next(
            (
                product
                for product in candidates
                if product["brand"] == top["brand"] and product.get("in_stock", False)
            ),
            None,
        )
        if recommended_product is None:
            continue
        recommended_product = {
            **recommended_product,
            "name": _natural_item_name(top["brand"], subcategory),
        }
        return {
            "status": RECOMMEND,
            "mention": mention,
            "subcategory": subcategory,
            "brand_source": "recommended",
            "brand": top["brand"],
            "available_brands": brand_options,
            "product": recommended_product,
            "message": (
                f"Our most popular {subcategory.lower()} is "
                f"{top['brand']} — would you like that?"
            ),
        }

    # --- Stage 2d: nothing to go on — ask ---
    return {
        "status": ASK,
        "mention": mention,
        "subcategory": subcategory,
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
    # Validate the subcategory — the agent supplies this arg and can
    # hallucinate (e.g. "Cookies" for "Biscuits"). Without this check,
    # search_products would fall back to $text and return unrelated hits,
    # producing a brand list that has nothing to do with what was asked.
    if not subcategory or not await db.products.find_one({"subcategory": subcategory}):
        return {
            "status": ASK,
            "subcategory": subcategory,
            "available_brands": [],
            "message": (
                f"Sorry, we don't carry {subcategory or 'that'} — "
                f"could you tell me what you'd like instead?"
            ),
        }

    candidates = await resolution.search_products(db, subcategory, limit=50)
    aliases_by_brand = _brand_alias_map(candidates)
    resolved_brand = _resolve_brand_name(brand or "", aliases_by_brand)

    for product in candidates:
        if product["brand"] == resolved_brand:
            return {
                "status": RESOLVED,
                "subcategory": subcategory,
                "brand_source": "mentioned",
                "product": product,
                "message": (
                    f"Got it — {_natural_item_name(product['brand'], subcategory)}."
                ),
            }
    brand_options = await _brand_options(db, subcategory)

    catalog_aliases = await _catalog_brand_alias_map(db)
    catalog_brand = _resolve_brand_name(brand or "", catalog_aliases)
    if catalog_brand is not None:
        alternate = await db.products.find_one(
            {"brand": catalog_brand, "in_stock": True},
            sort=[("popularity_score", -1)],
        )
        if alternate is not None:
            alternate_product = _serialize_product(alternate)
            options = _format_brand_options(brand_options)
            prefix = (
                f"For {subcategory.lower()}, we have {options}. " if options else ""
            )
            return {
                "status": ASK,
                "subcategory": subcategory,
                "available_brands": brand_options,
                "matched_brand": catalog_brand,
                "alternate_subcategory": alternate_product["subcategory"],
                "alternate_product": alternate_product,
                "brand_source": "mentioned",
                "message": (
                    f"{prefix}We carry {alternate_product['name']}, but it's "
                    f"listed as {alternate_product['subcategory'].lower()}, "
                    f"not {subcategory.lower()}. Would you like that instead?"
                ),
            }

    return {
        "status": ASK,
        "subcategory": subcategory,
        "available_brands": brand_options,
        "message": (
            f"Sorry, we don't have {brand} in {subcategory.lower()} — "
            f"is there another brand you'd like?"
        ),
    }
