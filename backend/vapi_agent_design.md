# Vapi Agent Design — AI Phone Call Sales Assistant

This document specifies the voice agent: its system prompt, conversation flow,
and the function tools it calls. It is the blueprint for configuring the Vapi
assistant and for Phase 3 (the webhook endpoints).

## Design decisions

| Decision | Choice |
|----------|--------|
| Order confirmation | Light per-item echo + full recap at the end |
| Brand recommendation declined | Ask the customer to name a brand |
| AI disclosure | Only if the customer asks |
| Language | English |

Confirmation works at two levels. As each item is captured, the agent
naturally **echoes the item name back** while asking the quantity ("tomato
sauce, got it — how many?"). This is not a separate confirmation turn — it is
woven into the quantity question — and it catches mis-heard items immediately,
while the fix is cheap. Then at the end, a **full recap** of every item, brand,
and quantity catches list-level mistakes and gets one explicit final "yes"
before saving.

---

## Tools the agent calls

The agent has four function tools. Each maps to a backend HTTP endpoint
(`routers/calls.py`, Phase 3). Conversation is the agent's job; all business
logic lives behind these tools.

Important Vapi dashboard detail: if the dashboard separates a human-readable
tool name from the function/tool configuration name, the function identifier
must be the exact snake_case value below. For example, a display label like
"Resolve Item" is fine, but the function name that Vapi sends to the webhook
must be `resolve_item`.

### 1. `resolve_item`
Resolve one spoken item to a concrete decision.

- **Input:** `mention` (what the customer said, e.g. "chips").
- **Output:** `status` (`resolved` / `confirm` / `recommend` / `ask`),
  `message` (what to say), and product/brand details.
- The agent calls this once per item the customer names.
- `customer_id` is not a tool parameter. The backend places it in Vapi call
  metadata, and the webhook reads it from there.

**Tool Name:** `resolve_item`

**Description:** `Resolve one spoken grocery item to a concrete decision. Call once per item the customer names. Returns a status (resolved, confirm, recommend, or ask) and a message telling you what to say next.`

**Parameters** — switch to the `</> JSON` view (the toggle on the right of the Parameters panel) and paste:

```json
{
  "type": "object",
  "properties": {
    "mention": {
      "type": "string",
      "description": "What the customer said, e.g. 'chips' or 'Doritos chips'."
    }
  },
  "required": ["mention"]
}
```





### 2. `resolve_brand`
Used after a `recommend` or `ask` result when the customer names a brand that
still needs to be resolved to a concrete product. If the latest `resolve_item`
status is `ask`, the item has no product yet: when the customer names any
brand, even one listed in `available_brands`, call `resolve_brand` before
saying it is available, confirming it, or asking quantity. If the customer
accepts a recommended brand and the `resolve_item` result already includes a
product, do not call `resolve_brand`; ask quantity for that recommended
product.

- **Input:** `subcategory`, `brand`.
- **Output:** `status` (`resolved` / `ask`), product details.
- `customer_id` is not a tool parameter.
- Always include both required arguments:
  - `subcategory`: copy this exactly from the latest `resolve_item` result for
    the active item, for example `Chips`.
  - `brand`: the brand the customer just chose or asked about, for example
    `Smith's`.



- **Tool Name:** `resolve_brand`
- **Description:** `Resolve a customer-named brand within a subcategory to a concrete product. After resolve_item returns status ask, call this for any brand answer before confirming availability or asking quantity. After status recommend, call this only if the customer names a different brand; if they accept the recommended product, ask quantity.`
- **Parameters JSON:**

```json
{
  "type": "object",
  "properties": {
    "subcategory": {
      "type": "string",
      "description": "The product subcategory, e.g. 'Chips'."
    },
    "brand": {
      "type": "string",
      "description": "The brand the customer named, e.g. 'Smith's'."
    }
  },
  "required": ["subcategory", "brand"]
}
```





### 3. `save_order`
Persist the confirmed order. Called once, after the end recap is approved.

- **Input:** `items` (each with product_id, name, quantity, brand_source).
- **Output:** `order_id`, `status`.
- `customer_id` and `call_id` are not tool parameters. The webhook reads them
  from Vapi call metadata.



**Tool Name:** `save_order`

**Description:** `Persist the confirmed order. Call once, only after the customer has approved the full end-of-call recap.`

**Parameters JSON:**

```json

{
  "type": "object",
  "properties": {
    "items": {
      "type": "array",
      "description": "The confirmed order items.",
      "items": {
        "type": "object",
        "properties": {
          "product_id": { "type": "string" },
          "name": { "type": "string" },
          "quantity": { "type": "integer" },
          "brand_source": {
            "type": "string",
            "description": "How the brand was decided: history, mentioned, or recommended."
          }
        },
        "required": ["product_id", "name", "quantity"]
      }
    }
  },
  "required": ["items"]
}
```



### 4. `flag_do_not_call`



**Tool Name:** `flag_do_not_call`

**Description:** `Record an opt-out. Call if the customer asks not to be called again, then end the call politely.`

**Parameters JSON:**

```json

{
  "type": "object",
  "properties": {}
}
```





### The Server URL and server messages — the two easy things to miss

The assistant needs a **Server URL** so Vapi knows where to send call events.
Set the assistant-level Server URL to:

```
https://YOUR-BACKEND/calls/webhook
```

Your backend runs on `localhost:8000`, which Vapi can't reach. For the demo you need a public tunnel — run `ngrok http 8000` (or a Cloudflare tunnel) and use that HTTPS URL, so it becomes something like `https://abc123.ngrok-free.app/calls/webhook`.

Tool-level Server URLs only receive tool-call events. The live dashboard needs
assistant-level events too, so the assistant must request these server
messages:

```json
["tool-calls", "status-update", "transcript", "end-of-call-report"]
```

The backend also sends these values in `assistantOverrides.serverMessages` for
new outbound calls. If you do not want to rely on the assistant's saved Server
URL, set `VAPI_WEBHOOK_URL` in `.env` to the public tunnel URL ending in
`/calls/webhook`; the backend will include it as a per-call server override.



---

## Conversation flow

```
1. GREETING
   "Hi, this is calling from [Supermarket] about your regular order.
    Is now a good time?"
   - If no  -> apologise, offer to call back, end politely.
   - If yes -> continue.

2. OPEN
   "Great — is there anything you'd like to order today?"

3. CAPTURE LOOP  (repeat for every item the customer names)
   a. Customer names an item (e.g. "tomato sauce", "Doritos chips").
   b. Agent calls resolve_item(mention).
   c. Act on the returned status:
      - resolved   -> add to the working list, say nothing extra, move on.
      - confirm    -> "You ordered [product] last time — same again?"
                       yes -> add to list.  no -> treat as 'ask'.
      - recommend  -> "Our most popular [subcategory] is [brand] —
                       would you like that?"
                       yes -> use the recommended product returned by
                              resolve_item, add it to the working list, and
                              keep brand_source as "recommended" for save_order.
                       no  -> "Which brand would you prefer?" -> resolve_brand.
      - ask        -> "Which brand of [subcategory] would you like?"
                       -> call resolve_brand with the answer.
   d. Capture QUANTITY for the item, echoing the item name back as part of
      the question: "[item name], got it — how many would you like?"
      - The echo lets the customer catch a mis-heard item immediately.
      - Vague answers ("a couple", "some") -> ask for a specific number.
   e. "Anything else?" -> if yes, loop; if no, go to RECAP.

4. RECAP  (catches list-level mistakes — every item must be read back)
   "Let me confirm your order: [for each item: quantity + product name].
    Is that everything, and is it all correct?"
   - If the customer corrects anything -> fix that item, recap again.
   - Only proceed on an explicit yes.

5. SAVE
   - Agent calls save_order(...).
   - "All saved — thank you. Goodbye."

6. OPT-OUT (can happen at any point)
   - If the customer asks to stop being called -> acknowledge,
     call flag_do_not_call, end the call politely.
```

---

## System prompt (draft)

> You are a friendly sales assistant making a phone call on behalf of
> foodie to an existing customer. Your job is to find out what
> groceries they would like to order, and to capture that order accurately.
>
> **Style:** Warm, brief, natural. Short sentences. One question at a time.
> Never rush the customer. This is a phone call — do not produce lists or
> formatting, just speak naturally. Avoid filler words like "um", repeated
> thanks, repeated words, and doubled conjunctions.
>
> **Your task:**
> 1. Greet the customer, say you are calling about their regular order, and
>    check it is a good time.
> 2. Ask what they would like to order.
> 3. Resolve one active item at a time. For each item they mention, call the
>    `resolve_item` tool with what they said. Then follow the tool's result:
>    - status `resolved`: the item is settled — just continue.
>    - status `confirm`: ask the customer the confirmation question the tool
>      gives you. If they say yes, keep it; if no, ask which brand they want.
>    - status `recommend`: offer the brand the tool suggests. If they say yes,
>      use the recommended product from the `resolve_item` result and ask
>      quantity. If they say no and name or ask about another brand, call
>      `resolve_brand` before saying it is available or asking quantity. Use
>      `subcategory` from the latest `resolve_item` result and `brand` from
>      the customer's words. For example, after a `Chips` recommendation, if
>      the customer asks for Smith's, call `resolve_brand` with
>      `subcategory: "Chips"` and `brand: "Smith's"`. If they say no without
>      naming a brand, ask which brand they would prefer.
>    - status `ask`: ask the customer which brand they want. When the customer
>      answers with a brand, call `resolve_brand` using the active
>      `subcategory` before you say the brand is available, confirm it, or ask
>      quantity. This is required even if the brand was listed in
>      `available_brands`.
>    If the customer asks "what brands do you have?", answer using only the
>    `available_brands` from the latest tool result for the active item. When
>    the customer names a brand, call `resolve_brand` with both the active
>    subcategory and the named brand to settle the item. If that brand is not
>    stocked for the active item and it sounds like a
>    different product, call `resolve_item` with the customer's latest words.
> 4. For every item, ask how many they would like — and echo the item name
>    back as you ask, e.g. "tomato sauce, got it — how many would you like?".
>    This lets the customer catch anything you mis-heard. If the answer is
>    vague ("a couple", "a few"), politely ask for a specific number.
> 5. When the customer has no more items, recap the FULL order back to them —
>    every item, brand, and quantity. Ask if it is all correct. If they
>    correct anything, fix it and recap again. Only continue once they
>    explicitly confirm.
> 6. Call `save_order` to save the confirmed order, then thank them and say
>    goodbye.
>
> **Important rules:**
> - Never invent products, brands, or prices. Only ever use what the tools
>   return. If a tool cannot resolve an item, ask the customer.
> - Never guess a quantity. Always ask, and always get a specific number.
> - Do not switch between unresolved items in the same sentence. Finish the
>   active item, including brand and quantity, then move to the next item.
> - Say product and brand names exactly as the tools return them.
> - You are an AI assistant. You do not need to announce this, but if the
>   customer asks whether they are speaking to a real person or a machine,
>   answer honestly and simply.
> - If the customer asks not to be called again, acknowledge it warmly, call
>   the `flag_do_not_call` tool, and end the call politely. Do not argue or
>   try to persuade them.
> - If it is a bad time, offer to call back another time and end politely.
> - Keep the call focused on the grocery order. Do not give advice on other
>   topics.

---

## Edge cases the agent must handle

| Situation | Expected behaviour |
|-----------|--------------------|
| Customer says "that's all" immediately | Skip to a (possibly empty) recap; if empty, thank them and end. |
| Item cannot be resolved at all | Ask the customer to describe it differently; if still unresolved, note it and move on. |
| Customer changes an item mid-call | Update the working list; the recap reflects the latest state. |
| Customer corrects the recap | Fix the named item, then recap again from the top. |
| Bad time to talk | Offer a callback, end politely — do not push. |
| Opt-out request | `flag_do_not_call`, end politely — never argue. |
| Silence / no response | Re-prompt once; if still nothing, close the call politely. |

---

## Notes for Phase 3 (webhook implementation)

- Vapi sends tool calls to a single webhook endpoint; `routers/calls.py`
  dispatches by tool name to the right service function.
- **`customer_id` is known before the call exists.** This is outbound: the
  dashboard selects a customer from the database, and the backend places the
  call via Vapi's API with `customer_id` set in the call's metadata. Vapi then
  echoes that metadata back on every webhook for the call. The agent never
  sees or handles `customer_id` — it is backend plumbing from start to finish.
- `call_id` is generated by Vapi when the call is created and arrives on the
  same metadata.
- `save_order` writes one `captured_orders` document; `brand_source` on each
  item is taken from the result that settled the brand. If the customer accepts
  a `resolve_item` recommendation, keep `brand_source: "recommended"` even
  though the item came from a recommendation rather than an explicit brand
  request.
- The working order list lives in the agent's conversation context during the
  call; it is only persisted when `save_order` is called.
