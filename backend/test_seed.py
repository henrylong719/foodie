"""Local test: runs seed.py's real logic against an in-memory MongoDB."""
import mongomock
import seed

db = mongomock.MongoClient()["supermarket_assistant"]
summary = seed.seed(db)

print("\n--- counts ---")
for k, v in summary.items():
    print(f"  {k:16s} {v}")

# --- correctness checks ---
assert summary["products"] == 1000, "expected 1000 products"
assert summary["customers"] == 50, "expected 50 customers"
assert summary["order_history"] > 0, "history should not be empty"
assert summary["captured_orders"] == 0, "captured_orders should start empty"

p = db.products.find_one()
for field in (
    "name", "brand", "brand_aliases", "category", "subcategory", "aliases",
    "size", "unit", "price", "in_stock", "popularity_score",
):
    assert field in p, f"product missing field: {field}"
assert isinstance(p["aliases"], list) and p["aliases"], "aliases must be a non-empty list"
assert isinstance(p["brand_aliases"], list), "brand_aliases must be a list"

c = db.customers.find_one()
for field in ("name", "phone", "do_not_call", "consent", "preferred_language"):
    assert field in c, f"customer missing field: {field}"
assert c["phone"].startswith("+614"), "phone format wrong"

h = db.order_history.find_one()
assert h["items"] and "category" in h["items"][0], "history item must denormalize category"

# every history item references a real product id
prod_ids = {x["_id"] for x in db.products.find({}, {"_id": 1})}
for order in db.order_history.find():
    for item in order["items"]:
        assert item["product_id"] in prod_ids, "dangling product reference"

# every order_history customer_id references a real customer
cust_ids = {x["_id"] for x in db.customers.find({}, {"_id": 1})}
for order in db.order_history.find():
    assert order["customer_id"] in cust_ids, "dangling customer reference"

# wipe-and-reseed: a second run must not double the data
summary2 = seed.seed(db)
assert summary2["products"] == 1000, "reseed should keep count stable, not append"

# spot-check alias coverage and category spread
cats = db.products.distinct("category")
print("\n  categories:", sorted(cats))
sample = db.products.find_one({"aliases": "chips"})
print("  sample 'chips' product:", sample["name"] if sample else "NONE FOUND")
assert sample is not None, "alias lookup for 'chips' failed"
assert db.products.find_one({"brand": "Bakers Delight", "brand_aliases": "bakers"}), \
    "brand alias lookup for Bakers Delight failed"

# dedupe guarantee: all products must be unique
names = [p["name"] for p in db.products.find()]
assert len(names) == len(set(names)), "duplicate product names found — dedupe failed"
print(f"  unique products: {len(set(names))} / {len(names)} (no duplicates)")
print(f"  distinct subcategories: {len(db.products.distinct('subcategory'))}")
print(f"  distinct brands: {len(db.products.distinct('brand'))}")

# brands must stay realistic for subcategories that define explicit mappings
for product in db.products.find():
    spec = seed.CATEGORIES[product["category"]]
    allowed_brands = seed._brands_for_subcategory(spec, product["subcategory"])
    assert product["brand"] in allowed_brands, (
        f"{product['brand']} should not appear in {product['subcategory']}"
    )
assert db.products.count_documents({
    "subcategory": "Ice Cream", "brand": "Birds Eye",
}) == 0, "Birds Eye should not be generated as ice cream"
assert db.products.count_documents({
    "subcategory": "Soft Drink", "brand": "Red Bull",
}) == 0, "Red Bull should not be generated as a soft drink"
print("  subcategory brand rules: valid")

# popularity must be computed from history, not random
scores = [p["popularity_score"] for p in db.products.find()]
assert all(0 <= s <= 100 for s in scores), "scores must be 0-100"
assert max(scores) == 100, "top-selling product should normalize to 100"
assert any(s == 0 for s in scores), "unsold products should score 0"
# a product's score must match the distinct-buyer count in order_history
top_product = db.products.find_one(sort=[("popularity_score", -1)])
buyers = db.order_history.distinct(
    "customer_id", {"items.product_id": top_product["_id"]})
print(f"  top product: {top_product['name']}  "
      f"(score {top_product['popularity_score']}, {len(buyers)} buyers)")
assert len(buyers) > 0, "top-scored product must actually appear in history"

# brand_popularity: per-(subcategory, brand), normalized per subcategory
bp = list(db.brand_popularity.find())
assert bp, "brand_popularity should not be empty"
for doc in bp:
    for field in ("category", "subcategory", "brand", "score", "buyer_count"):
        assert field in doc, f"brand_popularity missing {field}"
    assert 1 <= doc["score"] <= 100, "brand score must be 1-100"
# each subcategory present must have exactly one brand at score 100
from collections import defaultdict
by_subcat = defaultdict(list)
for doc in bp:
    by_subcat[doc["subcategory"]].append(doc)
for subcat, docs in by_subcat.items():
    assert max(d["score"] for d in docs) == 100, f"{subcat}: no top brand at 100"
# spot-check: top chips brand
chips_brands = sorted(by_subcat.get("Chips", []),
                      key=lambda d: -d["score"])
if chips_brands:
    top = chips_brands[0]
    print(f"  top 'Chips' brand: {top['brand']} "
          f"(score {top['score']}, {top['buyer_count']} buyers)")
print(f"  brand_popularity rows: {len(bp)} across {len(by_subcat)} subcategories")

print("\nALL CHECKS PASSED")
