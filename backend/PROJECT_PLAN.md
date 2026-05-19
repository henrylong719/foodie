# AI Phone Call Sales Assistant — Project Plan

## 1. Overview

An outbound AI voice agent that calls existing supermarket customers, asks if
they need anything, captures a shopping list conversationally, resolves vague
requests into real catalog products, confirms the list, and saves it as a
pending order for human fulfilment.

**Scope of v1 (demo):** capture and save a confirmed order list. No payment, no
pricing negotiation, no automated fulfilment.

### Tech stack

| Layer        | Technology   | Responsibility                                              |
|--------------|--------------|-------------------------------------------------------------|
| Voice        | Vapi         | Telephony, speech-to-text, LLM orchestration, text-to-speech |
| Backend      | Python (FastAPI) | Webhooks, function-call endpoints, business logic       |
| Database     | MongoDB      | Products, customers, order history, captured orders         |
| Frontend     | Next.js      | Dashboard: review orders, manage catalog, trigger calls     |
| Test data    | Tonic.ai     | Synthetic products, customers, order history                |

---

## 2. Goals and non-goals

### Goals
- Place outbound calls to existing customers and capture a shopping list.
- Resolve vague product mentions ("chips") into concrete catalog SKUs.
- Infer brand from order history first, then fall back to popularity.
- Confirm every item and quantity back to the customer before saving.
- Persist a structured, reviewable order.

### Non-goals (v1)
- Payment processing or order totals.
- Inbound calls.
- Multi-language support (English only).
- Real fulfilment / inventory deduction.
- High call volume — a demo-scale number of calls is sufficient.

---

## 3. The two hard problems

### 3.1 Brand / product resolution
A customer says "tomato sauce" — that is a category, not a SKU. The agent must
map free speech to real products via **function calling**: the Vapi LLM calls a
Python search endpoint mid-conversation that runs fuzzy + alias matching over
the catalog.

**Resolution decision tree (when no brand is mentioned):**
1. **History first** — search the customer's order history for that category.
   If found, confirm the specific past product:
   *"You ordered Smith's Crinkle Cut Cheese & Onion last time — same again?"*
2. **Popularity fallback** — if no history, recommend the highest
   `popularity_score` product in the category:
   *"Our most popular is X — would you like that?"*

### 3.2 Quantity accuracy
- Every item must carry an explicit quantity (default to 1 only after asking).
- The agent must read the **full list back** — item, brand, quantity — and get
  an explicit yes before saving.
- Ambiguous quantities ("a couple", "some") are clarified, not guessed.

---

## 4. Data model (MongoDB)

### `products`
```js
{
  _id, name, brand, category, subcategory,
  aliases: ["chips", "crisps", "potato chips"],  // what customers actually say
  size, unit, price, in_stock,
  popularity_score                               // 0-100, drives fallback
}
```

### `customers`
```js
{
  _id, name, phone,
  do_not_call,                                   // compliance flag
  consent: { given, date, method },
  preferred_language
}
```

### `order_history`
```js
{
  _id, customer_id, date,
  // category AND subcategory denormalized so brand inference can filter
  // at the right grain ("chips", not all "snacks")
  items: [ { product_id, name, category, subcategory, quantity } ]
}
```

### `brand_popularity` — brand ranking per subcategory
```js
{
  _id, category, subcategory, brand,
  score,        // 1-100, normalized within the subcategory
  buyer_count   // distinct customers who bought this brand here
}
```
Derived from `order_history`. Powers the no-brand recommendation fallback
("our most popular chips is Smith's"). Separate grain from product-level
popularity, so its own collection.

### `captured_orders` — the deliverable
```js
{
  _id, customer_id, call_id, created_at,
  status: "pending_fulfilment",
  items: [ { product_id, name, quantity, brand_source } ], // history|mentioned|recommended
  transcript_url
}
```

**Indexes:** `products` text index on `name`/`aliases`/`category`/`subcategory`,
plus `{ category, popularity_score }`; `order_history` compound index on
`{ customer_id, "items.subcategory" }`; `brand_popularity` index on
`{ subcategory, score }`; `customers` unique index on `phone`;
`captured_orders` indexes on `customer_id` and `created_at`.

**Two levels of popularity.** `products.popularity_score` ranks individual
SKUs (used by search ranking). The `brand_popularity` collection ranks brands
within a subcategory (used by the no-brand fallback). Both are computed from
`order_history` at seed time — in production the same aggregation runs on a
schedule.

The highest-leverage data work is hand-curating `aliases` for the top
subcategories.

---

## 5. Agent design (Vapi)

### Conversation flow
1. **Identify** — business name and purpose ("calling from XYZ Supermarket
   about your regular order").
2. **Open** — ask if the customer needs anything.
3. **Capture loop** — for each item: call search tool → resolve brand via the
   decision tree → confirm specifics and quantity.
4. **Recap** — read the full list back, item + brand + quantity.
5. **Save** — on explicit confirmation, call the save tool; close politely.
6. **Opt-out path** — if the customer asks to stop being called, trigger the
   opt-out tool and end the call.

### Function tools the agent calls
The agent calls four tools. Resolution logic (search, history, popularity) is
orchestrated behind `resolve_item` / `resolve_brand` so the agent makes simple
calls, not decisions.

| Tool                | Purpose                                                       |
|---------------------|---------------------------------------------------------------|
| `resolve_item`      | Resolve a spoken mention via the full decision tree           |
| `resolve_brand`     | Resolve a customer-named brand within a subcategory to a SKU  |
| `save_order`        | Persist the confirmed `captured_orders` document              |
| `flag_do_not_call`  | Record an opt-out request                                     |

The underlying HTTP endpoints (`/products/search`,
`/customers/{id}/history`) still exist and are used by the dashboard and tests
— but the agent itself only calls the four tools above.

See `VAPI_AGENT_DESIGN.md` for the full system prompt, conversation flow, and
edge-case handling.

---

## 6. Compliance (Australia)

Not legal advice — design constraints to build in from day one.

- **Existing Customer Relationship** keeps these calls on the right side of the
  Do Not Call Register Act 2006, since they target existing customers.
- **Scrub the Do Not Call Register** before dialling — honour the `do_not_call`
  flag on every customer regardless of the ECR exemption.
- **Identify** the business and purpose at the start of every call.
- **Honour opt-outs immediately** via the `flag_do_not_call` tool.
- **Respect calling hours** set by the Telemarketing Industry Standard 2017 —
  enforce in the dialer logic.
- **Privacy Act / APPs** apply to order data and call recordings.
- Disclosing the caller is AI is good practice, though not federally mandated
  for voice calls in Australia.

---

## 7. Build phases

| Phase | Deliverable                                                        | Status |
|-------|--------------------------------------------------------------------|--------|
| 0     | Seed script: 1000 products, 50 customers, order history, brand popularity | Done |
| 0b    | FastAPI backend skeleton: config, async Mongo, routers, /health    | Done |
| 1     | Resolution services: `search_products`, `get_customer_history`, `brand_popularity`, and the `resolve_item` orchestrator | Done |
| 2     | Vapi agent design: system prompt, flow, tools (`VAPI_AGENT_DESIGN.md`) | Done |
| 3     | Vapi webhook (`routers/calls.py`): `resolve_item`, `resolve_brand`, `save_order` dispatch; persist captured orders | Next |
| 4     | Next.js dashboard: review orders, manage catalog, trigger calls    | To do |
| 5     | Compliance logic: DNC scrubbing, calling hours, opt-out handling   | To do |
| 6     | End-to-end test calls; tune prompt and search ranking              | To do |

Note: the seed script replaced the Tonic.ai approach — a standalone script is
faster, reproducible, and has no external dependency for a demo.

---

## 8. Key risks

| Risk                                   | Mitigation                                       |
|----------------------------------------|--------------------------------------------------|
| Hallucinated SKUs                      | Function calling only; never list catalog in prompt |
| Poor alias coverage → bad matches      | Hand-curate aliases for top categories           |
| Wrong quantity captured                | Mandatory full-list recap before saving          |
| Customer speech misheard (STT errors)  | Confirm each item; recap step catches errors     |
| Compliance breach                      | DNC flag, calling-hours gate, opt-out tool        |

---

## 9. Open items to confirm later

- Vapi LLM/voice model choice and cost per call.
- How calls get triggered: manual from dashboard vs. batch queue.
- Transcript storage location (`transcript_url` source).
- Whether the dashboard needs auth for the demo.
