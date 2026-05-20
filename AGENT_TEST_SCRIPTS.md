# Agent Test Scripts

Manual QA scripts for testing the Foodie Vapi grocery-ordering agent.

These scripts are written from a product + QA perspective: each one describes
the customer behavior to simulate, the product risk being tested, the expected
agent behavior, and clear pass/fail checks.

## Assumptions

- The backend has seeded products, customers, order history, and
  `brand_popularity` data.
- The Vapi assistant is configured from `backend/VAPI_AGENT_DESIGN.md`.
- The assistant has these tool names exactly: `resolve_item`, `resolve_brand`,
  `save_order`, and `flag_do_not_call`.
- For live Vapi testing, the assistant-level server URL points to
  `/calls/webhook` through a public tunnel.
- The test customer has consent and is not marked `do_not_call`, unless the
  script specifically tests opt-out behavior.

## Test Scorecard

Use this quick scorecard after every call.

| Area | Pass criteria |
| --- | --- |
| Greeting | Identifies Foodie/supermarket purpose and asks if now is a good time. |
| One item at a time | Does not juggle multiple unresolved items in one response. |
| Product resolution | Calls `resolve_item` once per new item mention. |
| Brand handling | Uses history, explicit brand, popularity, or asks according to tool output. |
| Quantity handling | Always asks for a specific quantity; never guesses vague amounts. |
| Recap | Reads every item and quantity before saving. |
| Save behavior | Calls `save_order` only after explicit final confirmation. |
| Recovery | Handles corrections, unavailable brands, silence, and unknown items gracefully. |
| Trust | Does not invent brands, products, prices, or availability. |
| Compliance | Honors bad-time and do-not-call requests immediately. |

## Preflight Checks

Before live voice calls, run the backend checks so failures are easier to
triage.

```bash
cd backend
bash ./scripts/test.sh
```

Focused checks that exercise the agent tools:

```bash
cd backend
uv run python test_item_resolver.py
uv run python test_calls.py
```

Expected result: all checks pass. If these fail, fix the backend/tool layer
before tuning the Vapi prompt.

## Script 1: Basic Happy Path With Explicit Brand

**Risk tested:** Can the agent capture a straightforward branded item and save
only after recap confirmation?

**Customer script**

1. When greeted: "Yes, now is fine."
2. When asked what to order: "I need Doritos chips."
3. When asked quantity: "Two."
4. When asked anything else: "No, that's all."
5. At recap: "Yes, that's correct."

**Expected tool behavior**

- Calls `resolve_item` with `mention: "Doritos chips"`.
- Result should settle the item with brand source `mentioned`.
- Calls `save_order` after the customer confirms the recap.

**Pass criteria**

- Agent echoes the resolved product while asking quantity.
- Agent captures quantity `2`.
- Final recap includes `2` Doritos/chips product.
- No `save_order` call happens before the explicit "yes" at recap.

## Script 2: History-First Brand Confirmation

**Risk tested:** Vague item requests should use customer history before
popularity.

**Customer script**

1. "Yes, now is fine."
2. "I need chips."
3. If the agent asks whether you want the same as last time: "Yes."
4. Quantity: "One."
5. "That's all."
6. Recap confirmation: "Yes."

**Expected tool behavior**

- Calls `resolve_item` with `mention: "chips"`.
- If the customer has prior chips history, tool result should be `confirm`.
- Agent asks the confirmation question returned by the tool.
- After yes, the agent uses that product and asks quantity.

**Pass criteria**

- Agent does not jump directly to the most popular brand if history exists.
- Agent does not ask for brand again after the customer says yes to history.
- Saved item has `brand_source: "history"`.

## Script 3: Popularity Recommendation For New Customer

**Risk tested:** If no history exists, the agent recommends a popular brand but
still gets confirmation.

**Customer script**

1. "Yes, now is fine."
2. "Can I get chips?"
3. When the agent recommends a brand: "Yes, that's fine."
4. Quantity: "Three."
5. "Nothing else."
6. Recap confirmation: "Correct."

**Expected tool behavior**

- Calls `resolve_item` with `mention: "chips"`.
- For a customer with no matching history, result should be `recommend`.
- If customer accepts, agent resolves/uses the recommended brand and proceeds.
- Calls `save_order` only after recap.

**Pass criteria**

- Agent phrases the recommendation as a confirmation, not a fact already
  chosen by the customer.
- Saved item has `brand_source: "recommended"`.
- Agent never invents alternate brands beyond tool output.

## Script 4: Recommendation Declined, Customer Chooses Brand

**Risk tested:** Agent can recover when the customer rejects a recommended
brand and then names a preferred brand.

**Customer script**

1. "Yes, now is fine."
2. "I need chips."
3. When the agent recommends a brand: "No, do you have Smith's?"
4. Quantity: "Two packets."
5. "That's everything."
6. Recap confirmation: "Yes."

**Expected tool behavior**

- Calls `resolve_item` for `chips`.
- After rejection and brand preference, calls `resolve_brand` with:
  - `subcategory: "Potato Chips"`
  - `brand: "Smith's"` or the exact customer wording
- Saves the resolved Smith's product after recap.

**Pass criteria**

- Agent does not argue for the recommended brand.
- Agent does not call `resolve_item` again for "Smith's" unless the response
  sounds like a different product.
- Recap reflects the customer-selected brand.

## Script 5: Available Brands Question

**Risk tested:** Agent uses `available_brands` from the latest tool result and
does not hallucinate catalog options.

**Customer script**

1. "Yes."
2. "I need chips."
3. When asked/recommended a brand: "What brands do you have?"
4. Choose one offered brand: "Doritos."
5. Quantity: "One."
6. "No more."
7. Recap confirmation: "Yes."

**Expected tool behavior**

- Uses the latest `resolve_item` result for the active item.
- Answers available brands only from `available_brands`.
- Calls `resolve_brand` once the customer names a brand.

**Pass criteria**

- Agent gives a short brand list, not a long invented catalog.
- Agent does not mention prices.
- Agent returns to quantity capture after brand is resolved.

## Script 6: Unknown Item Recovery

**Risk tested:** Agent handles unresolved items without fabricating products.

**Customer script**

1. "Yes."
2. "I need dragonfruit cereal dust."
3. If asked to describe it differently: "Never mind, skip that."
4. Then say: "Actually, just get milk."
5. When asked which brand: "Pauls."
6. Give quantity: "One."
7. "That's all."
8. Recap confirmation: "Yes."

**Expected tool behavior**

- Calls `resolve_item` for the unknown phrase.
- If result is `ask`, agent asks for clarification.
- When customer skips it, the item is not included.
- Calls `resolve_item` for `milk`.
- When the customer names Pauls, calls `resolve_brand` with
  `subcategory: "Milk"` and `brand: "Pauls"` before asking quantity.

**Pass criteria**

- Unknown item is not saved.
- Agent does not invent a close product.
- Recap includes only the successfully resolved item.

## Script 7: Vague Quantity Clarification

**Risk tested:** Agent never guesses quantity.

**Customer script**

1. "Yes."
2. "I need Coke."
3. If the agent recommends Coca-Cola: "Yes."
4. Quantity response: "A couple."
5. If asked to clarify: "Two."
6. "That's it."
7. Recap confirmation: "Yes."

**Expected tool behavior**

- Calls `resolve_item` with `mention: "Coke"` or the transcript equivalent.
- Does not treat `Coke` as an explicit Coca-Cola brand mention; if Coca-Cola
  is used, it is because the customer accepted the recommendation.
- Agent asks for a specific number after "a couple".
- Saves quantity `2` only after the customer explicitly says "Two", not from
  the earlier vague phrase.

**Pass criteria**

- Agent does not silently interpret "a couple" without asking.
- Recap says `2` after the customer clarifies with "Two".

## Script 8: Mid-Call Item Correction

**Risk tested:** Agent can update the working list and recap the latest state.

**Customer script**

1. "Yes."
2. "I need Doritos chips."
3. Quantity: "Two."
4. When asked anything else: "Actually make that Smith's chips instead."
5. If asked quantity again: "Still two."
6. "That's all."
7. Recap confirmation: "Yes."

**Expected tool behavior**

- Initially resolves Doritos.
- On correction, resolves the new Smith's chips request.
- Final order contains Smith's, not Doritos.

**Pass criteria**

- Recap reflects the corrected item only.
- Agent does not save both Doritos and Smith's unless the customer clearly
  asks for both.

## Script 9: Recap Correction

**Risk tested:** Agent fixes recap mistakes and recaps again before saving.

**Customer script**

1. "Yes."
2. "I need Doritos chips."
3. Quantity: "Two."
4. "Also milk."
5. Quantity: "One."
6. At recap, say: "Actually make the chips three, not two."
7. At second recap: "Yes, that's right."

**Expected tool behavior**

- Resolves both items independently.
- Does not call `save_order` after the first failed recap.
- Updates chips quantity to `3`.
- Calls `save_order` only after the corrected recap is approved.

**Pass criteria**

- Final saved order has chips quantity `3`.
- Milk remains quantity `1`.
- Agent performs a second full recap.

## Script 10: Multi-Item In One Sentence

**Risk tested:** Agent resolves multiple requested items without losing brand
or quantity requirements.

**Customer script**

1. "Yes."
2. "I need Doritos chips, Coke, and milk."
3. Give quantities only when asked:
   - Doritos: "Two."
   - If the agent recommends Coca-Cola for Coke: "Yes."
   - Coke: "One."
   - Milk: "Three."
4. "That's everything."
5. Recap confirmation: "Yes."

**Expected tool behavior**

- Calls `resolve_item` separately for each item mention.
- Does not call `resolve_item` for Coke or milk until Doritos has a resolved
  product and quantity.
- Does not call `resolve_item` more than once for the same item.
- Does not treat `Coke` as an explicit Coca-Cola brand mention; if Coca-Cola
  is used, it is because the customer accepted the recommendation.
- Finishes brand and quantity for the active item before moving on.
- Saves all three items after recap.

**Pass criteria**

- No item is skipped.
- Agent does not assume quantities from the initial sentence.
- Recap is complete and easy to understand.

## Script 11: Bad Time To Talk

**Risk tested:** Agent respects customer availability and does not push.

**Customer script**

1. On greeting: "No, I'm busy right now."
2. If asked callback timing: "Tomorrow afternoon."

**Expected tool behavior**

- No product tools should be called.
- No order should be saved.
- Agent should politely offer/acknowledge a callback and end.

**Pass criteria**

- Call ends quickly.
- Agent does not try to continue the sales flow.

## Script 12: Do Not Call Opt-Out

**Risk tested:** Compliance path works immediately.

**Customer script**

1. On greeting or any later point: "Please don't call me again."

**Expected tool behavior**

- Calls `flag_do_not_call`.
- Does not call `resolve_item` or `save_order` after the opt-out.

**Pass criteria**

- Agent acknowledges the request without arguing.
- Customer record is marked `do_not_call`.
- Call ends politely.

## Script 13: AI Disclosure

**Risk tested:** Agent answers honestly if asked whether it is AI.

**Customer script**

1. "Are you a real person or an AI?"
2. After answer: "Okay, I need chips."
3. Continue with normal quantity and recap.

**Expected behavior**

- Agent gives a simple honest answer.
- Agent continues the order flow after disclosure.

**Pass criteria**

- No evasive answer.
- No long explanation that derails the call.

## Script 14: Silence Or No Response

**Risk tested:** Agent handles non-response without looping forever.

**Customer script**

1. Stay silent after the greeting.
2. If reprompted once, stay silent again.

**Expected behavior**

- Agent reprompts once.
- Agent ends politely if there is still no response.

**Pass criteria**

- No tool calls.
- No repeated prompting loop.

## Script 15: No Items Needed

**Risk tested:** Agent can close cleanly without creating an empty order unless
the product design intentionally wants empty orders saved.

**Customer script**

1. "Yes, now is fine."
2. "I don't need anything today."

**Expected behavior**

- Agent thanks the customer and ends.
- No `resolve_item` calls.
- No `save_order` call unless the product decision is to record empty calls.

**Pass criteria**

- No fake item is created.
- Call is short and polite.

## Debug Notes

If a test fails, classify it before changing anything:

| Symptom | Likely layer |
| --- | --- |
| Wrong product/brand returned by tool | Backend resolver, seed aliases, or popularity data |
| Tool never called | Vapi prompt/tool configuration |
| Tool call reaches backend but returns unknown tool | Tool name mismatch in Vapi dashboard |
| Agent saves before recap | Prompt/conversation policy |
| Agent invents brand or price | Prompt policy or model behavior |
| Transcript does not appear in dashboard | Vapi server messages, webhook URL, or SSE/dashboard layer |
| Opt-out spoken but customer not flagged | Prompt missed `flag_do_not_call` or webhook dispatch issue |

For every failed live call, capture:

- Vapi call id.
- Customer id used for the call.
- Transcript excerpt around the failure.
- Tool call payload and result.
- Whether the failure reproduced in `test_item_resolver.py` or `test_calls.py`.
