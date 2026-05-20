"""
Seed script for the AI Phone Call Sales Assistant.

Generates synthetic data and loads it into MongoDB Atlas:
  - 1000 products across supermarket categories, with curated aliases
  - 50 customers with consent records
  - order history per customer (the source for brand inference)
  - the captured_orders collection is created empty (filled by live calls)

Usage:
    export MONGODB_URI="mongodb+srv://user:pass@cluster.mongodb.net/"
    python seed.py

The script WIPES the target collections on every run, then reseeds.
"""

import os
import random
import sys
from datetime import datetime, timedelta, timezone

from pymongo import MongoClient, ASCENDING, TEXT

DB_NAME = "supermarket_assistant"
NUM_PRODUCTS = 1000
NUM_CUSTOMERS = 50

# --------------------------------------------------------------------------
# Catalog definition
#
# Each category carries the aliases customers actually say on the phone.
# This alias data is the single highest-leverage part of product resolution:
# it is what lets the search endpoint map "chips" to real SKUs.
# --------------------------------------------------------------------------
CATEGORIES = {
    "Snacks": {
        "subcategories": {
            "Chips": ["chips", "crisps", "potato chips", "corn chips", "tortilla chips", "hot chips"],
            "Crackers": ["crackers", "savoury biscuits", "water crackers"],
            "Chocolate": ["chocolate", "choccy", "chocolate bar", "block chocolate"],
            "Nuts": ["nuts", "mixed nuts", "snack nuts", "salted nuts"],
            "Popcorn": ["popcorn", "popping corn"],
            "Muesli Bars": ["muesli bars", "snack bars", "lunch box bars"],
        },
        "brands": ["Smith's", "Doritos", "Arnott's", "Cadbury", "Nobby's", "The Natural Confectionery Co"],
        "subcategory_brands": {
            "Chips": ["Smith's", "Doritos", "Nobby's"],
        },
        "units": ["packet"],
        "sizes": ["100g", "150g", "170g", "175g", "200g", "250g"],
    },
    "Beverages": {
        "subcategories": {
            "Soft Drink": [
                "soft drink", "soda", "fizzy drink", "pop", "coke", "cola",
                "coca cola", "coca-cola",
            ],
            "Juice": ["juice", "fruit juice", "orange juice", "apple juice"],
            "Water": ["water", "bottled water", "spring water", "sparkling water"],
            "Coffee": ["coffee", "instant coffee", "ground coffee", "coffee beans"],
            "Tea": ["tea", "tea bags", "black tea", "green tea"],
            "Energy Drink": ["energy drink", "energy", "sports drink"],
        },
        "brands": ["Coca-Cola", "Schweppes", "Golden Circle", "Mount Franklin", "Nescafe", "Lipton", "Red Bull"],
        "subcategory_brands": {
            "Soft Drink": ["Coca-Cola", "Schweppes"],
            "Juice": ["Golden Circle"],
            "Water": ["Mount Franklin"],
            "Coffee": ["Nescafe"],
            "Tea": ["Lipton"],
            "Energy Drink": ["Red Bull"],
        },
        "units": ["bottle", "can"],
        "sizes": ["375ml", "600ml", "1L", "1.25L", "2L"],
    },
    "Dairy": {
        "subcategories": {
            "Milk": ["milk", "fresh milk", "full cream milk", "skim milk"],
            "Cheese": ["cheese", "block cheese", "tasty cheese", "sliced cheese"],
            "Yoghurt": ["yoghurt", "yogurt", "yoghurt tub", "greek yoghurt"],
            "Butter": ["butter", "spread", "margarine"],
            "Cream": ["cream", "thickened cream", "pouring cream"],
            "Eggs": ["eggs", "free range eggs", "dozen eggs"],
        },
        "brands": ["Pauls", "Bega", "Dairy Farmers", "Western Star", "Chobani", "Devondale"],
        "units": ["bottle", "block", "tub", "carton"],
        "sizes": ["250g", "500g", "600ml", "1L", "2L"],
    },
    "Pantry": {
        "subcategories": {
            "Tomato Sauce": ["tomato sauce", "ketchup", "sauce", "tomato ketchup"],
            "Pasta": ["pasta", "spaghetti", "penne", "macaroni"],
            "Rice": ["rice", "white rice", "basmati", "jasmine rice"],
            "Cereal": ["cereal", "breakfast cereal", "muesli", "corn flakes"],
            "Canned Goods": ["canned food", "tinned food", "canned beans", "tinned tomatoes"],
            "Cooking Oil": ["oil", "cooking oil", "olive oil", "vegetable oil"],
            "Flour & Sugar": ["flour", "sugar", "baking", "plain flour"],
        },
        "brands": ["Heinz", "Leggo's", "San Remo", "SunRice", "Kellogg's", "Moccona", "Bertolli"],
        "units": ["bottle", "packet", "box", "can"],
        "sizes": ["250g", "375g", "500g", "750g", "1kg"],
    },
    "Frozen": {
        "subcategories": {
            "Ice Cream": ["ice cream", "icecream", "frozen dessert"],
            "Frozen Vegetables": ["frozen veggies", "frozen vegetables", "frozen peas"],
            "Frozen Pizza": ["pizza", "frozen pizza"],
            "Frozen Chips": ["frozen chips", "oven chips", "potato fries"],
            "Frozen Meals": ["frozen meals", "ready meals", "microwave meals"],
        },
        "brands": ["Streets", "Bulla", "Birds Eye", "McCain", "Peters", "Lean Cuisine"],
        "subcategory_brands": {
            "Ice Cream": ["Streets", "Bulla", "Peters"],
            "Frozen Vegetables": ["Birds Eye", "McCain"],
            "Frozen Pizza": ["McCain"],
            "Frozen Chips": ["McCain", "Birds Eye"],
            "Frozen Meals": ["Lean Cuisine", "McCain"],
        },
        "units": ["tub", "packet", "box", "each"],
        "sizes": ["375g", "500g", "1L", "1kg", "2L"],
    },
    "Household": {
        "subcategories": {
            "Dish Soap": ["dish soap", "dishwashing liquid", "detergent"],
            "Toilet Paper": ["toilet paper", "loo paper", "toilet rolls"],
            "Laundry": ["laundry powder", "washing powder", "laundry detergent"],
            "Paper Towel": ["paper towel", "kitchen towel", "paper roll"],
            "Cleaning Spray": ["cleaning spray", "surface spray", "cleaner"],
            "Bin Bags": ["bin bags", "garbage bags", "rubbish bags"],
        },
        "brands": ["Morning Fresh", "Quilton", "OMO", "Cuddly", "Sorbent", "Spray n' Wipe"],
        "units": ["bottle", "packet", "roll"],
        "sizes": ["500ml", "1L", "6 pack", "8 pack", "12 pack"],
    },
    "Bakery": {
        "subcategories": {
            "Bread": ["bread", "loaf", "sliced bread", "white bread"],
            "Rolls": ["rolls", "bread rolls", "buns", "dinner rolls"],
            "Wraps": ["wraps", "tortillas", "flatbread"],
            "Cakes": ["cake", "sponge cake", "muffins"],
            "Croissants": ["croissants", "pastries"],
        },
        "brands": ["Tip Top", "Wonder White", "Helga's", "Mission", "Bakers Delight"],
        "units": ["loaf", "packet", "each"],
        "sizes": ["6 pack", "8 pack", "500g", "650g", "700g"],
    },
    "Produce": {
        "subcategories": {
            "Apples": ["apples", "apple", "pink lady apples"],
            "Bananas": ["bananas", "banana"],
            "Potatoes": ["potatoes", "potato", "spuds"],
            "Tomatoes": ["tomatoes", "tomato", "fresh tomatoes"],
            "Lettuce": ["lettuce", "salad greens", "salad"],
            "Onions": ["onions", "onion", "brown onions"],
            "Carrots": ["carrots", "carrot"],
        },
        "brands": ["Fresh Produce", "Farmer's Choice", "Coles Fresh", "Harvest Select"],
        "units": ["each", "kg", "bag", "punnet"],
        "sizes": ["500g", "1kg", "2kg", "each"],
    },
    "Meat & Seafood": {
        "subcategories": {
            "Chicken": ["chicken", "chicken breast", "chicken thigh"],
            "Beef": ["beef", "beef mince", "steak"],
            "Pork": ["pork", "pork chops", "bacon"],
            "Lamb": ["lamb", "lamb chops"],
            "Fish": ["fish", "fish fillets", "salmon"],
            "Sausages": ["sausages", "snags", "bbq sausages"],
        },
        "brands": ["Butcher's Pride", "Ocean Catch", "Steggles", "Primo", "Lilydale"],
        "units": ["packet", "kg", "tray"],
        "sizes": ["300g", "500g", "750g", "1kg"],
    },
    "Health & Beauty": {
        "subcategories": {
            "Shampoo": ["shampoo", "hair wash"],
            "Soap": ["soap", "body wash", "hand wash"],
            "Toothpaste": ["toothpaste", "tooth paste"],
            "Deodorant": ["deodorant", "deo", "antiperspirant"],
            "Skincare": ["skincare", "moisturiser", "face cream", "lotion"],
        },
        "brands": ["Pantene", "Dove", "Colgate", "Rexona", "Nivea"],
        "units": ["bottle", "tube", "bar"],
        "sizes": ["100ml", "200ml", "250ml", "400ml"],
    },
    "Baby": {
        "subcategories": {
            "Nappies": ["nappies", "diapers", "baby nappies"],
            "Baby Wipes": ["baby wipes", "wipes"],
            "Baby Food": ["baby food", "puree", "infant food"],
            "Formula": ["formula", "baby formula", "infant formula"],
        },
        "brands": ["Huggies", "BabyLove", "Rafferty's Garden", "Aptamil"],
        "units": ["packet", "tub", "tin"],
        "sizes": ["120g", "250g", "500g", "24 pack", "48 pack"],
    },
    "Pet": {
        "subcategories": {
            "Dog Food": ["dog food", "dog biscuits", "puppy food"],
            "Cat Food": ["cat food", "kitten food"],
            "Pet Treats": ["pet treats", "dog treats", "cat treats"],
            "Cat Litter": ["cat litter", "kitty litter", "litter"],
        },
        "brands": ["Pedigree", "Whiskas", "Schmackos", "Purina", "Catsan"],
        "units": ["bag", "can", "packet"],
        "sizes": ["400g", "800g", "1.2kg", "3kg", "7kg"],
    },
}

DESCRIPTORS = [
    "Original", "Classic", "Light", "Extra", "Family Size", "Value",
    "Premium", "Reduced Fat", "No Added Sugar", "Twin Pack",
]

BRAND_ALIASES = {
    "Arnott's": ["arnotts"],
    "Bakers Delight": ["bakers"],
    "Butcher's Pride": ["butchers pride"],
    "Coca-Cola": ["coca cola", "coca-cola"],
    "Farmer's Choice": ["farmers choice"],
    "Helga's": ["helgas"],
    "Kellogg's": ["kelloggs"],
    "Leggo's": ["leggos"],
    "Nobby's": ["nobbys"],
    "Rafferty's Garden": ["raffertys garden"],
    "Red Bull": ["redbull"],
    "Smith's": ["smiths"],
    "Spray n' Wipe": ["spray n wipe", "spray and wipe"],
}


def _brands_for_subcategory(spec, subcategory):
    return spec.get("subcategory_brands", {}).get(subcategory, spec["brands"])


def _brand_aliases_for_brand(brand):
    return BRAND_ALIASES.get(brand, [])


def _product_name(brand, descriptor, subcategory, size):
    if subcategory == "Chips":
        chip_type = "Corn Chips" if brand == "Doritos" else "Potato Chips"
        return f"{brand} {descriptor} {chip_type} {size}"
    return f"{brand} {descriptor} {subcategory} {size}"


def generate_products(n=NUM_PRODUCTS):
    """Build n unique product documents spread across the catalog.

    Uniqueness is enforced on (brand, descriptor, subcategory, size). If the
    catalog cannot supply n distinct combinations, the function raises rather
    than silently returning fewer.
    """
    products = []
    seen = set()
    cat_names = list(CATEGORIES.keys())

    # cap = total distinct combinations the catalog can produce
    cap = sum(
        sum(
            len(_brands_for_subcategory(spec, subcat))
            for subcat in spec["subcategories"]
        ) * len(spec["sizes"]) * len(DESCRIPTORS)
        for spec in CATEGORIES.values()
    )
    if n > cap:
        raise ValueError(
            f"Requested {n} products but catalog only supports {cap} unique combinations."
        )

    i = 0
    attempts = 0
    while len(products) < n:
        attempts += 1
        cat = cat_names[i % len(cat_names)]
        i += 1
        spec = CATEGORIES[cat]
        subcat = random.choice(list(spec["subcategories"].keys()))
        brand = random.choice(_brands_for_subcategory(spec, subcat))
        size = random.choice(spec["sizes"])
        descriptor = random.choice(DESCRIPTORS)

        key = (brand, descriptor, subcat, size)
        if key in seen:
            continue                       # duplicate combination, skip
        seen.add(key)

        products.append({
            "name": _product_name(brand, descriptor, subcat, size),
            "brand": brand,
            "brand_aliases": _brand_aliases_for_brand(brand),
            "category": cat,
            "subcategory": subcat,
            "aliases": spec["subcategories"][subcat],
            "size": size,
            "unit": random.choice(spec["units"]),
            "price": round(random.uniform(1.5, 24.0), 2),
            "in_stock": random.random() > 0.05,
            # placeholder — overwritten by compute_popularity() from real
            # order history once orders exist. See seed().
            "popularity_score": 0,
        })
    return products


def generate_customers(n=NUM_CUSTOMERS):
    """Build n customer documents with consent records."""
    from faker import Faker
    fake = Faker("en_AU")
    customers = []
    phones = set()
    methods = ["in-store signup", "loyalty card registration", "online account"]
    while len(customers) < n:
        consent_date = datetime.now(timezone.utc) - timedelta(days=random.randint(30, 900))
        phone = "+614" + "".join(str(random.randint(0, 9)) for _ in range(8))
        if phone in phones:
            continue
        phones.add(phone)
        customers.append({
            "name": fake.name(),
            "phone": phone,
            "do_not_call": random.random() < 0.06,   # a few opted out
            "consent": {
                "given": True,
                "date": consent_date,
                "method": random.choice(methods),
            },
            "preferred_language": "en",
        })
    return customers


def generate_order_history(customers, products):
    """Build order history. Items denormalize category AND subcategory so
    brand-inference can filter at the right grain ("chips", not "snacks")."""
    history = []
    for customer in customers:
        for _ in range(random.randint(1, 6)):       # 1-6 past orders each
            order_date = datetime.now(timezone.utc) - timedelta(days=random.randint(1, 365))
            chosen = random.sample(products, random.randint(1, 5))
            items = [{
                "product_id": p["_id"],
                "name": p["name"],
                "category": p["category"],
                "subcategory": p["subcategory"],
                "quantity": random.randint(1, 4),
            } for p in chosen]
            history.append({
                "customer_id": customer["_id"],
                "date": order_date,
                "items": items,
            })
    return history


def compute_popularity(history):
    """Compute a 0-100 popularity_score per product from order history.

    This mirrors what a production system does: popularity is DERIVED from
    real purchase data, not hand-set. The signal here is the number of
    distinct customers who ordered each product (distinct customers, not raw
    quantity, so one bulk buyer can't dominate). Scores are normalized so the
    most-ordered product is 100.

    In production this same aggregation runs on a schedule (e.g. nightly) and
    writes the result back to products. Here it runs once at seed time.

    Returns: dict of product_id -> popularity_score (int 0-100).
    """
    # product_id -> set of customer_ids who ordered it
    buyers: dict = {}
    for order in history:
        customer_id = order["customer_id"]
        for item in order["items"]:
            buyers.setdefault(item["product_id"], set()).add(customer_id)

    counts = {pid: len(custs) for pid, custs in buyers.items()}
    if not counts:
        return {}

    top = max(counts.values())
    # normalize to 1-100; products never ordered stay at 0
    return {pid: max(1, round(c / top * 100)) for pid, c in counts.items()}


def compute_brand_popularity(history, products):
    """Compute brand popularity within each subcategory, from order history.

    Where compute_popularity() scores individual SKUs, this scores BRANDS
    within a subcategory — the unit the no-brand fallback actually needs.
    When a customer says "chips" with no brand and no history, the agent
    recommends the most popular *brand* of chips, not an over-specified SKU.

    Signal: distinct customers who ordered any product of that brand within
    the subcategory. Scores are normalized per subcategory so the top brand
    in each subcategory is 100.

    Returns: list of documents for the brand_popularity collection, shaped
        { category, subcategory, brand, score, buyer_count }.
    """
    # product_id -> (category, subcategory, brand) lookup
    info = {p["_id"]: (p["category"], p["subcategory"], p["brand"])
            for p in products}

    # (subcategory, brand) -> set of customer_ids; remember category too
    buyers: dict = {}
    cat_of: dict = {}
    for order in history:
        customer_id = order["customer_id"]
        for item in order["items"]:
            meta = info.get(item["product_id"])
            if meta is None:
                continue
            category, subcategory, brand = meta
            key = (subcategory, brand)
            buyers.setdefault(key, set()).add(customer_id)
            cat_of[key] = category

    # top buyer-count per subcategory, for per-subcategory normalization
    top_in_subcat: dict = {}
    for (subcategory, _brand), custs in buyers.items():
        top_in_subcat[subcategory] = max(top_in_subcat.get(subcategory, 0), len(custs))

    docs = []
    for (subcategory, brand), custs in buyers.items():
        count = len(custs)
        top = top_in_subcat[subcategory]
        docs.append({
            "category": cat_of[(subcategory, brand)],
            "subcategory": subcategory,
            "brand": brand,
            "score": max(1, round(count / top * 100)),
            "buyer_count": count,
        })
    return docs


def create_indexes(db):
    """Indexes that the search and history-lookup endpoints depend on."""
    db.products.create_index([
        ("name", TEXT), ("aliases", TEXT), ("brand_aliases", TEXT),
        ("category", TEXT), ("subcategory", TEXT),
    ], name="product_text_search")
    db.products.create_index([("category", ASCENDING), ("popularity_score", ASCENDING)])
    db.customers.create_index([("phone", ASCENDING)], unique=True)
    db.order_history.create_index([("customer_id", ASCENDING), ("items.subcategory", ASCENDING)])
    db.brand_popularity.create_index([("subcategory", ASCENDING), ("score", ASCENDING)])
    db.captured_orders.create_index([("customer_id", ASCENDING)])
    db.captured_orders.create_index([("created_at", ASCENDING)])
    # Idempotency: one captured order per Vapi call_id. Backstops the
    # early-return dedup in services.orders.save_order.
    db.captured_orders.create_index([("call_id", ASCENDING)], unique=True)


def seed(db):
    """Wipe and reseed all collections. Returns a summary dict."""
    print("WARNING: wiping existing collections in", db.name)
    for coll in ("products", "customers", "order_history",
                 "captured_orders", "brand_popularity"):
        db[coll].drop()

    products = generate_products()
    db.products.insert_many(products)        # insert_many sets _id in place

    customers = generate_customers()
    db.customers.insert_many(customers)

    history = generate_order_history(customers, products)
    db.order_history.insert_many(history)

    # popularity is derived from the order history just generated, then
    # written back onto the products — the same mechanism a production
    # nightly job uses, run once here at seed time.
    scores = compute_popularity(history)
    for product_id, score in scores.items():
        db.products.update_one(
            {"_id": product_id}, {"$set": {"popularity_score": score}}
        )

    # brand-level popularity within each subcategory — powers the no-brand
    # recommendation fallback. Separate grain, so its own collection.
    brand_pop = compute_brand_popularity(history, products)
    if brand_pop:
        db.brand_popularity.insert_many(brand_pop)

    create_indexes(db)

    scored = db.products.count_documents({"popularity_score": {"$gt": 0}})
    summary = {
        "products": db.products.count_documents({}),
        "products_with_sales": scored,
        "customers": db.customers.count_documents({}),
        "order_history": db.order_history.count_documents({}),
        "brand_popularity": db.brand_popularity.count_documents({}),
        "captured_orders": db.captured_orders.count_documents({}),
    }
    return summary


def main():
    uri = os.environ.get("MONGODB_URI")
    if not uri:
        sys.exit("ERROR: set the MONGODB_URI environment variable to your Atlas connection string.")
    client = MongoClient(uri)
    try:
        client.admin.command("ping")
    except Exception as exc:
        sys.exit(f"ERROR: could not connect to MongoDB: {exc}")

    summary = seed(client[DB_NAME])
    print("Seed complete. Document counts:")
    for coll, count in summary.items():
        print(f"  {coll:16s} {count}")


if __name__ == "__main__":
    main()
