# Demo Script

This script is designed for a clean Foodie demo with the current seeded
MongoDB data and the Vapi assistant configured from
`backend/VAPI_AGENT_DESIGN.md`.

- It assumes you reseeded the demo database with `backend/seed.py`.
- It keeps the main demo on the seeded Henry Long customer.
- It uses grocery items with strong catalog support: chips, ice cream, and
  Coke/soft drink.
- It makes the primary order path predictable by giving Henry recent purchase
  history for chips, ice cream, and Coke.

## Demo Account

The seed data always includes this callable demo customer:

- `Henry Long` - phone `+12176373205`
- Recent history:
  - `Doritos Original Corn Chips 170g`
  - `Streets Classic Ice Cream 2L`
  - `Coca-Cola Classic Soft Drink 1.25L`

Other Foodie customers are still generated randomly, so use them only for
optional branches.

- `Primary shopper` - `Henry Long`, status `callable`.
- `Optional recommendation shopper` - a callable non-Henry customer with no
  recent `Chips` history.
- `Optional opt-out shopper` - a different callable customer you can safely mark
  do-not-call during the demo.

Suggested quick MongoDB checks:

```javascript
// Stable demo customer
const henry = db.customers.findOne({ phone: "+12176373205" });
henry;

// Henry's demo history, newest first
db.order_history.find(
  { customer_id: henry._id },
  { date: 1, items: 1 }
).sort({ date: -1 }).limit(6);

// Other callable customers, for optional branches
db.customers.find(
  { do_not_call: false, phone: { $ne: "+12176373205" } },
  { name: 1, phone: 1, preferred_language: 1 }
).sort({ name: 1 }).limit(5);

// Callable customers with chips history
db.order_history.aggregate([
  { $unwind: "$items" },
  { $match: { "items.subcategory": "Chips" } },
  { $sort: { date: -1 } },
  {
    $group: {
      _id: "$customer_id",
      latest_chip_item: { $first: "$items.name" },
      latest_chip_date: { $first: "$date" }
    }
  },
  {
    $lookup: {
      from: "customers",
      localField: "_id",
      foreignField: "_id",
      as: "customer"
    }
  },
  { $unwind: "$customer" },
  { $match: { "customer.do_not_call": false } },
  {
    $project: {
      customer_id: "$_id",
      name: "$customer.name",
      phone: "$customer.phone",
      latest_chip_item: 1,
      latest_chip_date: 1
    }
  },
  { $limit: 5 }
]);

// In-stock products for the spoken demo paths
db.products.find(
  {
    in_stock: true,
    subcategory: { $in: ["Chips", "Ice Cream", "Soft Drink"] }
  },
  { name: 1, brand: 1, subcategory: 1, price: 1, popularity_score: 1 }
).sort({ subcategory: 1, popularity_score: -1 }).limit(12);
```

## Why These Paths Are Safe

- `chips` is a seeded alias for the `Chips` subcategory.
- `Doritos`, `Smith's`, and `Nobby's` are seeded chip brands.
- `ice cream` is a seeded alias for the `Ice Cream` subcategory.
- `Coke`, `cola`, and `soft drink` map to the `Soft Drink` subcategory.
- `Coca-Cola` and `Schweppes` are seeded soft drink brands.
- Henry has matching history for chips, ice cream, and soft drink, so the
  assistant should confirm each last-bought brand before using it.
- If you switch to a shopper with no matching history, the assistant should
  recommend the most popular available brand and ask the customer to accept it.

## Pre-Demo Checklist

1. Confirm `.env` is ready in `backend/`.
   - `MONGODB_URI` points to the demo Atlas database.
   - `DB_NAME=supermarket_assistant`.
   - For live calls, set `VAPI_API_KEY`, `VAPI_PHONE_NUMBER_ID`, and
     `VAPI_ASSISTANT_ID`.
   - If the demo is outside allowed Australia/Sydney calling hours, set
     `CALLING_HOURS_OVERRIDE=true`. This bypasses calling-hours only; it does
     not bypass do-not-call.
2. Reseed the database:

```bash
cd backend
uv run seed.py
```

3. Run the focused backend checks:

```bash
cd backend
bash ./scripts/test.sh
uv run python test_item_resolver.py
uv run python test_calls.py
```

4. Start the backend:

```bash
cd backend
uv run uvicorn app.main:app --reload
```

5. Start the frontend:

```bash
cd frontend
bun run dev
```

6. For a live voice demo, expose the backend webhook:

```bash
ngrok http 8000
```

Then set either the Vapi assistant Server URL or `VAPI_WEBHOOK_URL` to:

```text
https://YOUR-TUNNEL/calls/webhook
```

7. Open `http://localhost:3000`.
8. In `/customers`, find `Henry Long` and keep his row visible.
9. In `/catalog`, quickly confirm that there are in-stock items for Snacks,
   Frozen, and Beverages.
10. If no in-stock Doritos chips or ice cream product appears, swap that spoken
    item for an in-stock brand from the Catalog page.

Important dry-run note:

- If `VAPI_API_KEY` is blank, the dashboard can still show compliance, call
  creation, and call history, but no real phone call happens and no voice order
  will be captured.
- For the full spoken order demo, use live Vapi configuration.

## Part 1: Dashboard Readiness Walkthrough

Goal: show that Foodie has the data needed for outbound AI ordering.

Operator script:

```text
Open Overview.
Point out captured orders, customers, callable customers, and catalog items.

Open Catalog.
Filter to Snacks, Frozen, then Beverages.
Point out stock status, category/subcategory, price, and popularity.

Open Customers.
Find Henry Long and click Call.
```

Operator note:

- If the customer is do-not-call, the Call action should be hidden and the row
  should show a locked status.
- If the call is blocked for calling hours, turn on `CALLING_HOURS_OVERRIDE`
  and restart the backend before continuing.

## Part 2: Primary Shopper Places an Order

Goal: show a real outbound call, product resolution, quantity capture, recap,
and saved order.

Suggested spoken script:

```text
Customer: Yes, now is fine.

When asked what you would like to order:
Customer: I need chips, maybe some ice cream, and Coke.

If the assistant asks whether you want the Doritos chips you bought last time:
Customer: Yes, same as last time.

If the assistant recommends a chips brand:
Customer: Sure, that sounds fine.

If the assistant asks which brand of chips:
Customer: Doritos.

When asked quantity:
Customer: Two packets.

If the assistant asks whether you want the Streets ice cream you bought last time:
Customer: Yes, same as last time.

If the assistant asks which brand of ice cream:
Customer: Streets.

When asked quantity:
Customer: One tub.

If the assistant asks whether you want the Coca-Cola you bought last time:
Customer: Yes, same as last time.

If the assistant asks which brand of soft drink:
Customer: Coca-Cola.

When asked quantity:
Customer: Three bottles.

When asked if anything else:
Customer: That's all.

When the assistant reads the recap:
Customer: Yes, that's correct.
```

Operator note:

- The assistant should call `resolve_item` for each new item mention.
- The assistant should acknowledge the list once, then resolve chips, ice
  cream, and Coke one item at a time.
- If the customer says "etc." or "and stuff", the assistant should not guess
  extra items. It should finish the named items, then ask if anything else is
  needed.
- For Henry Long, chips, ice cream, and Coke should all go through
  history-confirmation behavior.
- If the assistant asks for a brand instead, the backup brands are Doritos,
  Streets, and Coca-Cola.
- The assistant should call `save_order` only after the final recap is approved.
- After the call ends, open `/orders` and review the newest captured order.

## Part 3: Optional Recommendation Branch

Goal: show the assistant making a recommendation without inventing one.

Use this part only if you want a second ordering call. Pick a callable
non-Henry shopper with no recent `Chips` history if you want to force the
recommendation path.

Suggested spoken script:

```text
Customer: Yes, now is fine.

Customer: I think I just need chips today.

If the assistant recommends the most popular chips brand:
Customer: Sure, that recommendation is fine.

When asked quantity:
Customer: One.

When asked if anything else:
Customer: No, that's everything for now.

When the assistant reads the recap:
Customer: Correct.
```

Operator note:

- If the customer has no chips history, the saved item should have
  `brand_source: "recommended"`.
- If the assistant finds chips history for this optional shopper, switch to a
  different callable shopper or treat the branch as another history-confirmation
  example.
- On `/orders`, recommended items are highlighted for review.

## Part 4: Customer Opts Out

Goal: show that Foodie honors do-not-call requests.

Use a different callable customer from the Primary shopper.

Suggested spoken script:

```text
Customer: Yes, I can hear you.

When the assistant explains the call:
Customer: Please don't call me again.

If the assistant confirms the opt-out:
Customer: Yes, please mark me do-not-call.
```

Operator note:

- The assistant should call `flag_do_not_call`.
- Refresh `/customers`; that shopper should be locked/do-not-call.
- Do not use this same customer again for the main order demo.

## Backup Lines

Use these only if the conversation branches.

- `Could you repeat the options?`
- `Yes, same as last time.`
- `Yes, that recommendation is fine.`
- `What brands do you have?`
- `I'll take Coca-Cola.`
- `I only meant the items I named.`
- `Make that two, exactly.`
- `Sorry, I meant ice cream.`
- `Skip that item.`
- `No, that's everything.`
- `Yes, the recap is correct.`

## What Success Looks Like

- The dashboard places an outbound call only for a callable customer.
- The call detail page shows a live or saved transcript.
- The assistant handles a multi-item opening request without losing items.
- The assistant resolves customer-mentioned brands without extra questioning.
- Vague items use customer history first, then popularity recommendation.
- The assistant asks for exact quantities and does not guess vague amounts.
- The assistant reads a full recap before saving.
- `/orders` shows a new `pending_fulfillment` order with item quantities and
  brand source labels.
- Opt-out requests update the customer to do-not-call and prevent future UI
  dialing.
