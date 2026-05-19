# Foodie Vapi Smoke Eval Setup

This file translates the manual QA scripts in
[AGENT_TEST_SCRIPTS.md](../AGENT_TEST_SCRIPTS.md) into practical Vapi
`chat.mockConversation` evals for the Foodie grocery-ordering assistant.

Use these evals with the assistant configured from
[VAPI_AGENT_DESIGN.md](./VAPI_AGENT_DESIGN.md).

## General Setup

For each eval:

1. Create a new evaluation in Vapi.
2. Add the `User` messages in the order shown.
3. Add `Tool Response` turns where this file provides mocked tool output.
4. Add `Assistant` turns exactly where the workflow lists them.
5. Set `Approach` per assistant turn: `LLM-as-a-judge` for conversational
   checkpoints, or exact expected-tool-call validation for deterministic tool
   calls.
6. Keep `Include Conversation Context` turned on.

Only add a `Tool Response` turn after the immediately previous assistant turn
actually initiated the matching tool call. If the assistant did not call the
expected tool, do not paste the tool response; the checkpoint should fail.

Important Vapi checker rule: use exact expected-tool-call validation only for
flat deterministic arguments such as `resolve_brand.subcategory`,
`resolve_brand.brand`, and empty opt-out arguments. Vapi's expected-tool-call
UI does not support nested array arguments, so do not use exact validation for
`save_order.items`. Check `save_order` semantically with an LLM-as-a-judge
turn instead.

Also do not exact-match free-form speech arguments such as
`resolve_item.mention`; the assistant may correctly normalize "I need Doritos
chips" as `Doritos chips`, `Doritos`, or `chips`. Check those semantically with
an LLM-as-a-judge turn.

Use this base template for every LLM-as-a-judge prompt. Add the prompt's
`Pass criteria` and `Fail criteria` between the decision rule and output
format:

```text
You are an LLM-Judge. Evaluate ONLY the last assistant message in the mock conversation: {{messages[-1]}}.
Context is available in {{messages}}, but your judgment must focus on the last assistant message.

Decision rule:
- PASS if ALL "pass criteria" are satisfied AND NONE of the "fail criteria" are triggered.
- Otherwise FAIL.

Pass criteria:
- [add criteria for this assistant turn]

Fail criteria:
- [add criteria for this assistant turn]

Output format: respond with exactly one word: pass or fail
- No explanations
- No punctuation
- No additional text
```

## How To Read Assistant Turns

Yes: when a workflow says something like
```
`Assistant`: should ask what the customer wants to order.
```
that means you should add an `Assistant` turn in Vapi and evaluate it with
LLM-as-a-judge.

Use this dashboard shape for conversational checkpoints:

```text
Assistant
Mock: off
Evaluation: on
Approach: LLM-as-a-judge
Checkpoint: the assistant should ask what the customer wants to order.
```

Use this dashboard shape for deterministic tool-call checkpoints:

```text
Assistant
Mock: off
Evaluation: on
Approach: exact expected tool call
Expected tool/function: resolve_brand
Expected arguments: subcategory = Chips, brand = Smith's
```

Do not use that exact expected-tool-call checker for `save_order`; its `items`
argument is a nested array. Use the save-order LLM judge template below.

Use LLM-as-a-judge for:

- Conversational behavior, like asking for quantity or recapping.
- Negative behavior, like not pushing after a bad-time response.
- Free-form speech arguments, like `resolve_item.mention`.
- Tool calls whose arguments include fuzzy text.

Use exact expected-tool-call validation only for deterministic arguments:

- `resolve_brand.subcategory`
- `resolve_brand.brand` when the spoken brand is explicit
- `flag_do_not_call` with no arguments

Use this LLM-as-a-judge template for `resolve_item` tool-call checkpoints.
Important: a customer naming an item, including a vague item like "chips",
is exactly when the assistant should call `resolve_item`. Do not fail the
assistant for using resolution before adding the item; resolution is required
to map speech to a catalog product.

```text
You are an LLM-Judge. Evaluate ONLY the last assistant message in the mock conversation: {{messages[-1]}}.
Context is available in {{messages}}, but your judgment must focus on the last assistant message.

Decision rule:
- PASS if ALL "pass criteria" are satisfied AND NONE of the "fail criteria" are triggered.
- Otherwise FAIL.

Pass criteria:
- The last assistant message calls the `resolve_item` tool.
- The tool call is for the customer's latest requested item: [paste requested item, e.g. chips].
- It is acceptable if `resolve_item.mention` is a semantic normalization rather than an exact quote.

Fail criteria:
- The last assistant message does not call `resolve_item`.
- The last assistant message asks for quantity, recommends a brand, confirms an item, or adds an item before tool resolution.
- The tool call is for a different item than the customer's latest request.
- The judgment fails merely because the customer made a simple item request; simple item requests still require `resolve_item`.

Output format: respond with exactly one word: pass or fail
- No explanations
- No punctuation
- No additional text
```

For intermediate conversational turns, use the checkpoint sentence in this
template:

```text
You are an LLM-Judge. Evaluate ONLY the last assistant message in the mock conversation: {{messages[-1]}}.
Context is available in {{messages}}, but your judgment must focus on the last assistant message.

Decision rule:
- PASS if ALL "pass criteria" are satisfied AND NONE of the "fail criteria" are triggered.
- Otherwise FAIL.

Pass criteria:
- The assistant satisfies this checkpoint:
[paste the checkpoint sentence from the workflow]

Fail criteria:
- The assistant does not satisfy the checkpoint, jumps to an unrelated flow, or calls a tool that the checkpoint forbids.

Output format: respond with exactly one word: pass or fail
- No explanations
- No punctuation
- No additional text
```

For `save_order` turns, use LLM-as-a-judge because Vapi cannot exact-match the
nested `items` array. Paste the expected item rows from the case into this
template:

```text
You are an LLM-Judge. Evaluate ONLY the last assistant message in the mock conversation: {{messages[-1]}}.
Context is available in {{messages}}, but your judgment must focus on the last assistant message.

Decision rule:
- PASS if ALL "pass criteria" are satisfied AND NONE of the "fail criteria" are triggered.
- Otherwise FAIL.

Pass criteria:
- The last assistant message calls the save_order tool.
- The save_order call includes exactly the expected order items listed below.
- Each expected item has the correct product_id, quantity, and brand_source.

Expected order items:
- [paste expected product_id, quantity, and brand_source rows from the case]

Fail criteria:
- The last assistant message does not call save_order.
- The save_order call is missing any expected item.
- The save_order call includes an extra item not approved in the recap.
- Any expected item's product_id, quantity, or brand_source is wrong.

Output format: respond with exactly one word: pass or fail
- No explanations
- No punctuation
- No additional text
```

Do not use a final judge prompt to re-grade earlier assistant turns. With this
template, every LLM-as-a-judge prompt should describe the expected behavior of
the assistant turn it is attached to. Use exact validation or an intermediate
LLM judge turn at the moment a tool call or behavior happens. The case-level
`Judge Prompt` below is for the final assistant message only.

## Shared Mock Products

Use these stable IDs in mocked tool responses and `save_order` expectations.
Keep `product.name` conversational and size-free; put package size in a
separate `size` field so the assistant does not say SKU sizes aloud.

| Product | Mock product_id |
| --- | --- |
| Doritos Cheese Corn Chips | `prod-doritos-chips-170g` |
| Smith's Original Potato Chips | `prod-smiths-chips-150g` |
| Coca-Cola Classic Soft Drink | `prod-coke-125l` |
| Pauls Full Cream Milk | `prod-pauls-milk-2l` |

Mock response labels may be reused across evals. When a later eval says
`paste DORITOS_RESOLVED`, use the JSON block with that label from the first
case that defines it.

## Save Order Expectations

When a workflow says to add the save-order LLM judge checkpoint, use the
save-order template above. Paste the matching rows from this table into the
`Expected order items` section. Only paste the `ORDER_SAVED` tool response
after the assistant actually calls `save_order`.

| Eval | Expected `save_order` items |
| --- | --- |
| SMK-01 | `prod-doritos-chips-170g`, quantity `2`, brand_source `mentioned` |
| SMK-02 | `prod-smiths-chips-150g`, quantity `1`, brand_source `history` |
| SMK-03 | `prod-doritos-chips-170g`, quantity `3`, brand_source `recommended` |
| SMK-04 | `prod-smiths-chips-150g`, quantity `2`, brand_source `mentioned` |
| SMK-05 | `prod-smiths-chips-150g`, quantity `1`, brand_source `mentioned` |
| SMK-06 | `prod-pauls-milk-2l`, quantity `1`, brand_source `mentioned` |
| SMK-07 | `prod-coke-125l`, quantity `2`, brand_source `mentioned` |
| SMK-08 | `prod-smiths-chips-150g`, quantity `2`, brand_source `mentioned` |
| SMK-09 | `prod-doritos-chips-170g`, quantity `3`, brand_source `mentioned`; `prod-pauls-milk-2l`, quantity `1`, brand_source `mentioned` |
| SMK-10 | `prod-doritos-chips-170g`, quantity `2`, brand_source `mentioned`; `prod-coke-125l`, quantity `1`, brand_source `mentioned`; `prod-pauls-milk-2l`, quantity `3`, brand_source `mentioned` |
| SMK-13 | `prod-smiths-chips-150g`, quantity `1`, brand_source `history` |

## SMK-01 Basic Happy Path With Explicit Brand

Goal: verify the assistant captures a straightforward branded item, asks for
quantity, recaps, and saves only after explicit approval.

### Exact Vapi Workflow

This first eval is written in the expanded dashboard style. Later evals use the
same settings, but keep the wording shorter.

1. `User`
   `Yes, now is fine.`

2. `Assistant`
   `Mock`: off
   `Evaluation`: on
   `Approach`: `LLM-as-a-judge`
   Check that the assistant asks what the customer wants to order.

3. `User`
   `I need Doritos chips.`

4. `Assistant`
   `Mock`: off
   `Evaluation`: on
   `Approach`: `LLM-as-a-judge`
   Check that the assistant calls `resolve_item` for the Doritos/chips request.
   Paste `DORITOS_RESOLVED` only after that tool call actually happens.
   Do not use exact validation for `resolve_item.mention`.

5. `Tool Response`
   Paste `DORITOS_RESOLVED`.

6. `Assistant`
   `Mock`: off
   `Evaluation`: on
   `Approach`: `LLM-as-a-judge`
   Check that the assistant asks for a specific quantity while echoing the
   Doritos/chips item.

7. `User`
   `Two.`

8. `Assistant`
   `Mock`: off
   `Evaluation`: on
   `Approach`: `LLM-as-a-judge`
   Check that the assistant captures quantity 2 and asks whether anything else
   is needed.

9. `User`
   `No, that's all.`

10. `Assistant`
    `Mock`: off
    `Evaluation`: on
    `Approach`: `LLM-as-a-judge`
    Check that the assistant recaps exactly one Doritos/chips item with
    quantity 2 and asks for confirmation.

11. `User`
    `Yes, that's correct.`

12. `Assistant`
    `Mock`: off
    `Evaluation`: on
    `Approach`: `LLM-as-a-judge`
    Check that the assistant calls `save_order` with the expected item rows in
    the Save Order Checkpoint below. Paste `ORDER_SAVED` only after that tool
    call actually happens.

13. `Tool Response`
    Paste `ORDER_SAVED`.

14. `Assistant`
    `Mock`: off
    `Evaluation`: on
    `Approach`: `LLM-as-a-judge`
    This is the final checkpoint. Use the Judge Prompt below.

### Mock Tool Responses

`DORITOS_RESOLVED`

```json
{"status":"resolved","mention":"Doritos chips","subcategory":"Chips","brand_source":"mentioned","product":{"_id":"prod-doritos-chips-170g","name":"Doritos Cheese Corn Chips","brand":"Doritos","category":"Snacks","subcategory":"Chips","size":"170g","unit":"packet"},"message":"Got it — Doritos Cheese Corn Chips."}
```

`ORDER_SAVED`

```json
{"ok":true,"order_id":"order-smk-01"}
```

### Save Order Checkpoint

Use LLM-as-a-judge for this `save_order` turn. Do not use exact validation;
Vapi does not support nested array arguments.

Expected order items:

- `product_id = prod-doritos-chips-170g`
- `quantity = 2`
- `brand_source = mentioned`

Do not exact-match `resolve_item.mention`.

### Judge Prompt

```text
You are an LLM-Judge. Evaluate ONLY the last assistant message in the mock conversation: {{messages[-1]}}.
Context is available in {{messages}}, but your judgment must focus on the last assistant message.

Decision rule:
- PASS if ALL "pass criteria" are satisfied AND NONE of the "fail criteria" are triggered.
- Otherwise FAIL.

Pass criteria:
- The last assistant message briefly confirms the order was saved.
- The last assistant message sounds like a polite closing after a completed order.
- The last assistant message does not ask for more ordering details after the order has been saved.

Fail criteria:
- The last assistant message says or implies the order failed when the tool response was successful.
- The last assistant message invents products, brands, prices, or availability not present in the conversation.
- The last assistant message reopens the order flow instead of closing politely.

Output format: respond with exactly one word: pass or fail
- No explanations
- No punctuation
- No additional text
```

## SMK-02 History-First Brand Confirmation

Goal: vague item requests should use customer history before popularity.

### Exact Vapi Workflow

1. `User`: `Yes, now is fine.`
2. `Assistant`: asks what the customer wants.
3. `User`: `I need chips.`
4. `Assistant`: add a `resolve_item` LLM-as-a-judge checkpoint for the
   customer request `chips`. Paste `CHIPS_HISTORY_CONFIRM` only after the
   assistant actually calls `resolve_item`.
5. `Tool Response`: paste `CHIPS_HISTORY_CONFIRM`.
6. `Assistant`: asks whether the customer wants Smith's again.
7. `User`: `Yes.`
8. `Assistant`: asks quantity.
9. `User`: `One.`
10. `Assistant`: asks anything else.
11. `User`: `That's all.`
12. `Assistant`: recaps.
13. `User`: `Yes.`
14. `Assistant`: add the save-order LLM judge checkpoint using the expected
    item rows below.
15. `Tool Response`: paste `ORDER_SAVED`.
16. `Assistant`: evaluated final checkpoint.

### Mock Tool Responses

`CHIPS_HISTORY_CONFIRM`

```json
{"status":"confirm","mention":"chips","subcategory":"Chips","brand_source":"history","product":{"_id":"prod-smiths-chips-150g","name":"Smith's Original Potato Chips","brand":"Smith's","category":"Snacks","subcategory":"Chips","size":"150g","unit":"packet"},"message":"You ordered Smith's Original Potato Chips last time — would you like that again?"}
```

`ORDER_SAVED`

```json
{"ok":true,"order_id":"order-smk-02"}
```

### Save Order Checkpoint

Use LLM-as-a-judge for this `save_order` turn. Do not use exact validation;
Vapi does not support nested array arguments.

Expected order items:

- `product_id = prod-smiths-chips-150g`
- `quantity = 1`
- `brand_source = history`

### Judge Prompt

```text
You are an LLM-Judge. Evaluate ONLY the last assistant message in the mock conversation: {{messages[-1]}}.
Context is available in {{messages}}, but your judgment must focus on the last assistant message.

Decision rule:
- PASS if ALL "pass criteria" are satisfied AND NONE of the "fail criteria" are triggered.
- Otherwise FAIL.

Pass criteria:
- The last assistant message briefly confirms the order was saved.
- The last assistant message sounds like a polite closing after a completed order.
- The last assistant message does not ask for more ordering details after the order has been saved.

Fail criteria:
- The last assistant message says or implies the order failed when the tool response was successful.
- The last assistant message invents products, brands, prices, or availability not present in the conversation.
- The last assistant message reopens the order flow instead of closing politely.

Output format: respond with exactly one word: pass or fail
- No explanations
- No punctuation
- No additional text
```

## SMK-03 Popularity Recommendation Accepted

Goal: if no history exists, the assistant recommends a popular brand, confirms
acceptance, then captures quantity for the recommended product.

### Exact Vapi Workflow

1. `User`: `Yes, now is fine.`
2. `Assistant`: asks what the customer wants.
3. `User`: `Can I get chips?`
   - This is intentionally a simple, vague item request with no brand.
   - Expected behavior: the assistant must resolve it through the catalog
     before asking quantity or adding it to the order.
4. `Assistant`: add an LLM-as-a-judge checkpoint using the exact
   `resolve_item` judge prompt in Tool Validation below. This turn should pass
   only when the assistant calls `resolve_item` for the chips request.
5. `Tool Response`: paste `CHIPS_RECOMMEND_DORITOS`.
6. `Assistant`: recommends Doritos and asks if that works.
7. `User`: `Yes, that's fine.`
8. `Assistant`: asks quantity, using the natural item label
   `Doritos chips`, for example: `Doritos chips, got it — how many would you
   like?`
   - Do not add a tool-call checkpoint here.
   - Do not paste `DORITOS_BRAND_RESOLVED` in this eval.
9. `User`: `Three.`
10. `Assistant`: asks anything else.
11. `User`: `Nothing else.`
12. `Assistant`: recaps.
13. `User`: `Correct.`
14. `Assistant`: add the save-order LLM judge checkpoint using the expected
    SMK-03 item row from the Save Order Expectations table.
15. `Tool Response`: paste `ORDER_SAVED`.
16. `Assistant`: evaluated final checkpoint.

### Mock Tool Responses

`CHIPS_RECOMMEND_DORITOS`

```json
{"status":"recommend","mention":"chips","subcategory":"Chips","brand_source":"recommended","brand":"Doritos","available_brands":["Doritos","Smith's"],"product":{"_id":"prod-doritos-chips-170g","name":"Doritos chips","brand":"Doritos","category":"Snacks","subcategory":"Chips","size":"170g","unit":"packet"},"message":"Our most popular chips is Doritos — would you like that?"}
```

`ORDER_SAVED`

```json
{"ok":true,"order_id":"order-smk-03"}
```

### Tool Validation

For step 4, add an `Assistant` turn in Vapi with:

- `Mock`: off
- `Evaluation`: on
- `Approach`: `LLM-as-a-judge`

Use this exact judge prompt:

```text
You are an LLM-Judge. Evaluate ONLY the last assistant message in the mock conversation: {{messages[-1]}}.
Context is available in {{messages}}, but your judgment must focus on the last assistant message.

Decision rule:
- PASS if ALL "pass criteria" are satisfied AND NONE of the "fail criteria" are triggered.
- Otherwise FAIL.

Pass criteria:
- The last assistant message calls the `resolve_item` tool.
- The tool call is for the customer's latest requested item: chips.
- It is acceptable if `resolve_item.mention` is `chips`, `Can I get chips`, or another semantic normalization of the customer's chips request.

Fail criteria:
- The last assistant message does not call `resolve_item`.
- The last assistant message asks for quantity, recommends a brand, confirms an item, or adds chips before tool resolution.
- The tool call is for a different item than chips.
- The judgment fails merely because the customer made a simple item request; simple item requests still require `resolve_item`.

Output format: respond with exactly one word: pass or fail
- No explanations
- No punctuation
- No additional text
```

For step 8, add an `Assistant` turn in Vapi with:

- `Mock`: off
- `Evaluation`: on
- `Approach`: `LLM-as-a-judge`

Use this exact judge prompt:

```text
You are an LLM-Judge. Evaluate ONLY the last assistant message in the mock conversation: {{messages[-1]}}.
Context is available in {{messages}}, but your judgment must focus on the last assistant message.

Decision rule:
- PASS if ALL "pass criteria" are satisfied AND NONE of the "fail criteria" are triggered.
- Otherwise FAIL.

Pass criteria:
- The last assistant message asks how many chips the customer would like.
- The last assistant message uses the natural item label `Doritos chips`.
- The last assistant message does not mention package size, SKU size, product id, or `Doritos Cheese Corn Chips`.

Fail criteria:
- The last assistant message calls a tool.
- The last assistant message asks about a different item.
- The last assistant message skips the quantity question.
- The last assistant message says `170g`, `prod-doritos-chips-170g`, or `Doritos Cheese Corn Chips`.

Output format: respond with exactly one word: pass or fail
- No explanations
- No punctuation
- No additional text
```

For the `save_order` turn, use LLM-as-a-judge. Do not use exact validation;
Vapi does not support nested array arguments.

Expected order items:

- `product_id = prod-doritos-chips-170g`
- `quantity = 3`
- `brand_source = recommended`

### Judge Prompt

```text
You are an LLM-Judge. Evaluate ONLY the last assistant message in the mock conversation: {{messages[-1]}}.
Context is available in {{messages}}, but your judgment must focus on the last assistant message.

Decision rule:
- PASS if ALL "pass criteria" are satisfied AND NONE of the "fail criteria" are triggered.
- Otherwise FAIL.

Pass criteria:
- The last assistant message briefly confirms the order was saved.
- The last assistant message sounds like a polite closing after a completed order.
- The last assistant message does not ask for more ordering details after the order has been saved.

Fail criteria:
- The last assistant message says or implies the order failed when the tool response was successful.
- The last assistant message invents products, brands, prices, or availability not present in the conversation.
- The last assistant message reopens the order flow instead of closing politely.

Output format: respond with exactly one word: pass or fail
- No explanations
- No punctuation
- No additional text
```

## SMK-04 Recommendation Declined, Customer Chooses Brand

Goal: the assistant should recover when a recommendation is declined and the
customer names a preferred brand.

### Exact Vapi Workflow

1. `User`: `Yes, now is fine.`
2. `Assistant`: asks what the customer wants.
3. `User`: `I need chips.`
4. `Assistant`: add a `resolve_item` LLM-as-a-judge checkpoint for the
   customer request `chips`. Paste `CHIPS_RECOMMEND_DORITOS` only after the
   assistant actually calls `resolve_item`.
5. `Tool Response`: paste `CHIPS_RECOMMEND_DORITOS`.
6. `Assistant`: recommends Doritos.
7. `User`: `No, do you have Smith's?`
8. `Assistant`: add an exact expected-tool-call checkpoint for
   `resolve_brand` with `subcategory = Chips` and `brand = Smith's`. This turn
   should pass only when the assistant calls `resolve_brand` before claiming
   Smith's is available or asking quantity.
   - The tool call must include both arguments. The active subcategory comes
     from the prior `resolve_item` response: `subcategory = Chips`.
   - The brand comes from the customer's latest message:
     `brand = Smith's`.
9. `Tool Response`: paste `SMITHS_BRAND_RESOLVED`.
10. `Assistant`: asks quantity.
11. `User`: `Two packets.`
12. `Assistant`: asks anything else.
13. `User`: `That's everything.`
14. `Assistant`: recaps.
15. `User`: `Yes.`
16. `Assistant`: add the save-order LLM judge checkpoint using the expected
    SMK-04 item row from the Save Order Expectations table.
17. `Tool Response`: paste `ORDER_SAVED`.
18. `Assistant`: evaluated final checkpoint.

### Mock Tool Responses

`CHIPS_RECOMMEND_DORITOS`

```json
{"status":"recommend","mention":"chips","subcategory":"Chips","brand_source":"recommended","brand":"Doritos","available_brands":["Doritos","Smith's"],"product":{"_id":"prod-doritos-chips-170g","name":"Doritos chips","brand":"Doritos","category":"Snacks","subcategory":"Chips","size":"170g","unit":"packet"},"message":"Our most popular chips is Doritos — would you like that?"}
```

`SMITHS_BRAND_RESOLVED`

```json
{"status":"resolved","subcategory":"Chips","brand_source":"mentioned","product":{"_id":"prod-smiths-chips-150g","name":"Smith's Original Potato Chips","brand":"Smith's","category":"Snacks","subcategory":"Chips","size":"150g","unit":"packet"},"message":"Got it — Smith's Original Potato Chips."}
```

`ORDER_SAVED`

```json
{"ok":true,"order_id":"order-smk-04"}
```

### Save Order Checkpoint

For step 8, add an `Assistant` turn in Vapi with:

- `Mock`: off
- `Evaluation`: on
- `Approach`: exact expected tool call
- Expected tool/function: `resolve_brand`
- Expected arguments:
  - `subcategory = Chips`
  - `brand = Smith's`

Only add the following `Tool Response` turn after this assistant turn has
actually initiated the `resolve_brand` tool call. If the assistant says
Smith's is available or asks quantity without a tool call, the assistant
skipped brand resolution and this checkpoint should fail.
If the assistant calls `resolve_brand` but omits either `subcategory = Chips`
or `brand = Smith's`, this checkpoint should also fail.

Use LLM-as-a-judge for this `save_order` turn. Do not use exact validation;
Vapi does not support nested array arguments.

Expected order items:

- `product_id = prod-smiths-chips-150g`
- `quantity = 2`
- `brand_source = mentioned`

### Judge Prompt

```text
You are an LLM-Judge. Evaluate ONLY the last assistant message in the mock conversation: {{messages[-1]}}.
Context is available in {{messages}}, but your judgment must focus on the last assistant message.

Decision rule:
- PASS if ALL "pass criteria" are satisfied AND NONE of the "fail criteria" are triggered.
- Otherwise FAIL.

Pass criteria:
- The last assistant message briefly confirms the order was saved.
- The last assistant message sounds like a polite closing after a completed order.
- The last assistant message does not ask for more ordering details after the order has been saved.

Fail criteria:
- The last assistant message says or implies the order failed when the tool response was successful.
- The last assistant message invents products, brands, prices, or availability not present in the conversation.
- The last assistant message reopens the order flow instead of closing politely.

Output format: respond with exactly one word: pass or fail
- No explanations
- No punctuation
- No additional text
```

## SMK-05 Available Brands Question

Goal: when the customer asks what brands are available, the assistant should
use only `available_brands` from the latest tool response.

### Exact Vapi Workflow

1. `User`: `Yes.`
2. `Assistant`: asks what the customer wants.
3. `User`: `I need chips.`
4. `Assistant`: add a `resolve_item` LLM-as-a-judge checkpoint for the
   customer request `chips`. Paste `CHIPS_RECOMMEND_DORITOS` only after the
   assistant actually calls `resolve_item`.
5. `Tool Response`: paste `CHIPS_RECOMMEND_DORITOS`.
6. `Assistant`: recommends Doritos.
7. `User`: `What brands do you have?`
8. `Assistant`: lists only Doritos and Smith's, then asks which brand.
9. `User`: `Smith's.`
10. `Assistant`: add an exact expected-tool-call checkpoint for
    `resolve_brand` with `subcategory = Chips` and `brand = Smith's`. Paste
    `SMITHS_BRAND_RESOLVED` only after that tool call happens.
11. `Tool Response`: paste `SMITHS_BRAND_RESOLVED`.
12. `Assistant`: asks quantity.
13. `User`: `One.`
14. `Assistant`: asks anything else.
15. `User`: `No more.`
16. `Assistant`: recaps.
17. `User`: `Yes.`
18. `Assistant`: add the save-order LLM judge checkpoint using the expected
    SMK-05 item row from the Save Order Expectations table.
19. `Tool Response`: paste `ORDER_SAVED`.
20. `Assistant`: evaluated final checkpoint.

### Mock Tool Responses

Use `CHIPS_RECOMMEND_DORITOS`, `SMITHS_BRAND_RESOLVED`, and:

```json
{"ok":true,"order_id":"order-smk-05"}
```

### Judge Prompt

```text
You are an LLM-Judge. Evaluate ONLY the last assistant message in the mock conversation: {{messages[-1]}}.
Context is available in {{messages}}, but your judgment must focus on the last assistant message.

Decision rule:
- PASS if ALL "pass criteria" are satisfied AND NONE of the "fail criteria" are triggered.
- Otherwise FAIL.

Pass criteria:
- The last assistant message briefly confirms the order was saved.
- The last assistant message sounds like a polite closing after a completed order.
- The last assistant message does not ask for more ordering details after the order has been saved.

Fail criteria:
- The last assistant message says or implies the order failed when the tool response was successful.
- The last assistant message invents products, brands, prices, or availability not present in the conversation.
- The last assistant message reopens the order flow instead of closing politely.

Output format: respond with exactly one word: pass or fail
- No explanations
- No punctuation
- No additional text
```

## SMK-06 Unknown Item Recovery

Goal: unresolved items should not be fabricated or saved; the assistant should
recover and continue with a later valid item.

### Exact Vapi Workflow

1. `User`: `Yes.`
2. `Assistant`: asks what the customer wants.
3. `User`: `I need dragonfruit cereal dust.`
4. `Assistant`: add a `resolve_item` LLM-as-a-judge checkpoint for the
   customer request `dragonfruit cereal dust`. Paste `UNKNOWN_ITEM_ASK` only
   after the assistant actually calls `resolve_item`.
5. `Tool Response`: paste `UNKNOWN_ITEM_ASK`.
6. `Assistant`: asks the customer to describe it differently.
7. `User`: `Never mind, skip that.`
8. `Assistant`: acknowledges skip and asks if anything else is needed.
9. `User`: `Actually, just get milk.`
10. `Assistant`: add a `resolve_item` LLM-as-a-judge checkpoint for the
    customer request `milk`. Paste `MILK_ASK_BRAND` only after the assistant
    actually calls `resolve_item`.
11. `Tool Response`: paste `MILK_ASK_BRAND`.
12. `Assistant`: asks which milk brand.
13. `User`: `Pauls.`
14. `Assistant`: add an exact expected-tool-call checkpoint for
    `resolve_brand` with `subcategory = Milk` and `brand = Pauls`. Paste
    `PAULS_MILK_RESOLVED` only after that tool call happens.
15. `Tool Response`: paste `PAULS_MILK_RESOLVED`.
16. `Assistant`: asks quantity.
17. `User`: `One.`
18. `Assistant`: asks anything else.
19. `User`: `That's all.`
20. `Assistant`: recaps.
21. `User`: `Yes.`
22. `Assistant`: add the save-order LLM judge checkpoint using the expected
    SMK-06 item row from the Save Order Expectations table.
23. `Tool Response`: paste `ORDER_SAVED`.
24. `Assistant`: evaluated final checkpoint.

### Mock Tool Responses

`UNKNOWN_ITEM_ASK`

```json
{"status":"ask","mention":"dragonfruit cereal dust","message":"I couldn't find 'dragonfruit cereal dust' — could you describe it differently?"}
```

`MILK_ASK_BRAND`

```json
{"status":"ask","mention":"milk","subcategory":"Milk","available_brands":["Pauls","Dairy Farmers","Devondale"],"next_tool":"resolve_brand","next_tool_instruction":"When the customer names a brand for this item, call resolve_brand with this subcategory and the customer's brand before asking quantity.","message":"Which brand of milk would you like?"}
```

`PAULS_MILK_RESOLVED`

```json
{"status":"resolved","subcategory":"Milk","brand_source":"mentioned","product":{"_id":"prod-pauls-milk-2l","name":"Pauls Full Cream Milk","brand":"Pauls","category":"Dairy","subcategory":"Milk","size":"2L","unit":"bottle"},"message":"Got it — Pauls Full Cream Milk."}
```

`ORDER_SAVED`

```json
{"ok":true,"order_id":"order-smk-06"}
```

### Judge Prompt

```text
You are an LLM-Judge. Evaluate ONLY the last assistant message in the mock conversation: {{messages[-1]}}.
Context is available in {{messages}}, but your judgment must focus on the last assistant message.

Decision rule:
- PASS if ALL "pass criteria" are satisfied AND NONE of the "fail criteria" are triggered.
- Otherwise FAIL.

Pass criteria:
- The last assistant message briefly confirms the order was saved.
- The last assistant message sounds like a polite closing after a completed order.
- The last assistant message does not mention or save the skipped unknown item.

Fail criteria:
- The last assistant message says or implies the order failed when the tool response was successful.
- The last assistant message invents a product for the skipped unknown item.
- The last assistant message reopens the order flow instead of closing politely.

Output format: respond with exactly one word: pass or fail
- No explanations
- No punctuation
- No additional text
```

## SMK-07 Vague Quantity Clarification

Goal: the assistant should not silently interpret vague quantity language.

### Exact Vapi Workflow

1. `User`: `Yes.`
2. `Assistant`: asks what the customer wants.
3. `User`: `I need Coke.`
4. `Assistant`: add a `resolve_item` LLM-as-a-judge checkpoint for the
   customer request `Coke`. Paste `COKE_RESOLVED` only after the assistant
   actually calls `resolve_item`.
5. `Tool Response`: paste `COKE_RESOLVED`.
6. `Assistant`: asks quantity.
7. `User`: `A couple.`
8. `Assistant`: asks for a specific number.
9. `User`: `Two.`
10. `Assistant`: asks anything else.
11. `User`: `That's it.`
12. `Assistant`: recaps.
13. `User`: `Yes.`
14. `Assistant`: add the save-order LLM judge checkpoint using the expected
    SMK-07 item row from the Save Order Expectations table.
15. `Tool Response`: paste `ORDER_SAVED`.
16. `Assistant`: evaluated final checkpoint.

### Mock Tool Responses

`COKE_RESOLVED`

```json
{"status":"resolved","mention":"Coke","subcategory":"Soft Drink","brand_source":"mentioned","product":{"_id":"prod-coke-125l","name":"Coca-Cola Classic Soft Drink","brand":"Coca-Cola","category":"Beverages","subcategory":"Soft Drink","size":"1.25L","unit":"bottle"},"message":"Got it — Coca-Cola Classic Soft Drink."}
```

`ORDER_SAVED`

```json
{"ok":true,"order_id":"order-smk-07"}
```

### Judge Prompt

```text
You are an LLM-Judge. Evaluate ONLY the last assistant message in the mock conversation: {{messages[-1]}}.
Context is available in {{messages}}, but your judgment must focus on the last assistant message.

Decision rule:
- PASS if ALL "pass criteria" are satisfied AND NONE of the "fail criteria" are triggered.
- Otherwise FAIL.

Pass criteria:
- The last assistant message briefly confirms the order was saved.
- The last assistant message sounds like a polite closing after a completed order.
- The last assistant message does not ask for more ordering details after the order has been saved.

Fail criteria:
- The last assistant message says or implies the order failed when the tool response was successful.
- The last assistant message invents products, brands, prices, or availability not present in the conversation.
- The last assistant message reopens the order flow instead of closing politely.

Output format: respond with exactly one word: pass or fail
- No explanations
- No punctuation
- No additional text
```

## SMK-08 Mid-Call Item Correction

Goal: the assistant should update the working list when the customer replaces
one item with another.

### Exact Vapi Workflow

1. `User`: `Yes.`
2. `Assistant`: asks what the customer wants.
3. `User`: `I need Doritos chips.`
4. `Assistant`: add a `resolve_item` LLM-as-a-judge checkpoint for the
   customer request `Doritos chips`. Paste `DORITOS_RESOLVED` only after the
   assistant actually calls `resolve_item`.
5. `Tool Response`: paste `DORITOS_RESOLVED`.
6. `Assistant`: asks quantity.
7. `User`: `Two.`
8. `Assistant`: asks anything else.
9. `User`: `Actually make that Smith's chips instead.`
10. `Assistant`: add a `resolve_item` LLM-as-a-judge checkpoint for the
    corrected customer request `Smith's chips`. Paste `SMITHS_RESOLVED` only
    after the assistant actually calls `resolve_item` for the correction.
11. `Tool Response`: paste `SMITHS_RESOLVED`.
12. `Assistant`: asks or confirms the quantity for Smith's.
13. `User`: `Still two.`
14. `Assistant`: asks anything else.
15. `User`: `That's all.`
16. `Assistant`: recaps.
17. `User`: `Yes.`
18. `Assistant`: add the save-order LLM judge checkpoint using the expected
    SMK-08 item row from the Save Order Expectations table.
19. `Tool Response`: paste `ORDER_SAVED`.
20. `Assistant`: evaluated final checkpoint.

### Mock Tool Responses

`DORITOS_RESOLVED`

```json
{"status":"resolved","mention":"Doritos chips","subcategory":"Chips","brand_source":"mentioned","product":{"_id":"prod-doritos-chips-170g","name":"Doritos Cheese Corn Chips","brand":"Doritos","category":"Snacks","subcategory":"Chips","size":"170g","unit":"packet"},"message":"Got it — Doritos Cheese Corn Chips."}
```

`SMITHS_RESOLVED`

```json
{"status":"resolved","mention":"Smith's chips","subcategory":"Chips","brand_source":"mentioned","product":{"_id":"prod-smiths-chips-150g","name":"Smith's Original Potato Chips","brand":"Smith's","category":"Snacks","subcategory":"Chips","size":"150g","unit":"packet"},"message":"Got it — Smith's Original Potato Chips."}
```

`ORDER_SAVED`

```json
{"ok":true,"order_id":"order-smk-08"}
```

### Judge Prompt

```text
You are an LLM-Judge. Evaluate ONLY the last assistant message in the mock conversation: {{messages[-1]}}.
Context is available in {{messages}}, but your judgment must focus on the last assistant message.

Decision rule:
- PASS if ALL "pass criteria" are satisfied AND NONE of the "fail criteria" are triggered.
- Otherwise FAIL.

Pass criteria:
- The last assistant message briefly confirms the order was saved.
- The last assistant message sounds like a polite closing after a completed order.
- The last assistant message does not mention Doritos as part of the final saved order.

Fail criteria:
- The last assistant message says or implies the order failed when the tool response was successful.
- The last assistant message treats Doritos as still ordered after the customer replaced it.
- The last assistant message reopens the order flow instead of closing politely.

Output format: respond with exactly one word: pass or fail
- No explanations
- No punctuation
- No additional text
```

## SMK-09 Recap Correction

Goal: if the customer corrects the recap, the assistant should update the
order, recap again, and save only after the corrected recap is approved.

### Exact Vapi Workflow

1. `User`: `Yes.`
2. `Assistant`: asks what the customer wants.
3. `User`: `I need Doritos chips.`
4. `Assistant`: add a `resolve_item` LLM-as-a-judge checkpoint for the
   customer request `Doritos chips`. Paste `DORITOS_RESOLVED` only after the
   assistant actually calls `resolve_item`.
5. `Tool Response`: paste `DORITOS_RESOLVED`.
6. `Assistant`: asks quantity.
7. `User`: `Two.`
8. `Assistant`: asks anything else.
9. `User`: `Also Pauls milk.`
10. `Assistant`: add a `resolve_item` LLM-as-a-judge checkpoint for the
    customer request `Pauls milk`. Paste `PAULS_MILK_RESOLVED` only after the
    assistant actually calls `resolve_item`.
11. `Tool Response`: paste `PAULS_MILK_RESOLVED`.
12. `Assistant`: asks quantity.
13. `User`: `One.`
14. `Assistant`: asks anything else.
15. `User`: `That's all.`
16. `Assistant`: recaps two Doritos and one Pauls milk.
17. `User`: `Actually make the chips three, not two.`
18. `Assistant`: recaps three Doritos and one Pauls milk.
19. `User`: `Yes, that's right.`
20. `Assistant`: add the save-order LLM judge checkpoint using the expected
    SMK-09 item rows from the Save Order Expectations table.
21. `Tool Response`: paste `ORDER_SAVED`.
22. `Assistant`: evaluated final checkpoint.

### Mock Tool Responses

Use `DORITOS_RESOLVED`, `PAULS_MILK_RESOLVED`, and:

```json
{"ok":true,"order_id":"order-smk-09"}
```

### Judge Prompt

```text
You are an LLM-Judge. Evaluate ONLY the last assistant message in the mock conversation: {{messages[-1]}}.
Context is available in {{messages}}, but your judgment must focus on the last assistant message.

Decision rule:
- PASS if ALL "pass criteria" are satisfied AND NONE of the "fail criteria" are triggered.
- Otherwise FAIL.

Pass criteria:
- The last assistant message briefly confirms the order was saved.
- The last assistant message sounds like a polite closing after a completed order.
- If the last assistant message mentions the order details, it reflects the corrected chips quantity of 3.

Fail criteria:
- The last assistant message says or implies the order failed when the tool response was successful.
- The last assistant message repeats the incorrect chips quantity of 2 as the final order.
- The last assistant message reopens the order flow instead of closing politely.

Output format: respond with exactly one word: pass or fail
- No explanations
- No punctuation
- No additional text
```

## SMK-10 Multi-Item In One Sentence

Goal: the assistant should resolve each item separately and collect quantities
one active item at a time.

### Exact Vapi Workflow

1. `User`: `Yes.`
2. `Assistant`: asks what the customer wants.
3. `User`: `I need Doritos chips, Coke, and Pauls milk.`
4. `Assistant`: add a `resolve_item` LLM-as-a-judge checkpoint for
   `Doritos chips`. Paste `DORITOS_RESOLVED` only after the assistant actually
   calls `resolve_item` for Doritos chips.
5. `Tool Response`: paste `DORITOS_RESOLVED`.
6. `Assistant`: asks Doritos quantity.
7. `User`: `Two.`
8. `Assistant`: add a `resolve_item` LLM-as-a-judge checkpoint for `Coke`.
   Paste `COKE_RESOLVED` only after the assistant actually calls
   `resolve_item` for Coke.
9. `Tool Response`: paste `COKE_RESOLVED`.
10. `Assistant`: asks Coke quantity.
11. `User`: `One.`
12. `Assistant`: add a `resolve_item` LLM-as-a-judge checkpoint for
    `Pauls milk`. Paste `PAULS_MILK_RESOLVED` only after the assistant
    actually calls `resolve_item` for Pauls milk.
13. `Tool Response`: paste `PAULS_MILK_RESOLVED`.
14. `Assistant`: asks milk quantity.
15. `User`: `Three.`
16. `Assistant`: asks anything else.
17. `User`: `That's everything.`
18. `Assistant`: recaps all three items.
19. `User`: `Yes.`
20. `Assistant`: add the save-order LLM judge checkpoint using the expected
    SMK-10 item rows from the Save Order Expectations table.
21. `Tool Response`: paste `ORDER_SAVED`.
22. `Assistant`: evaluated final checkpoint.

### Mock Tool Responses

Use `DORITOS_RESOLVED`, `COKE_RESOLVED`, `PAULS_MILK_RESOLVED`, and:

```json
{"ok":true,"order_id":"order-smk-10"}
```

### Judge Prompt

```text
You are an LLM-Judge. Evaluate ONLY the last assistant message in the mock conversation: {{messages[-1]}}.
Context is available in {{messages}}, but your judgment must focus on the last assistant message.

Decision rule:
- PASS if ALL "pass criteria" are satisfied AND NONE of the "fail criteria" are triggered.
- Otherwise FAIL.

Pass criteria:
- The last assistant message briefly confirms the order was saved.
- The last assistant message sounds like a polite closing after a completed order.
- If the last assistant message mentions the order details, it includes Doritos, Coke, and Pauls milk.

Fail criteria:
- The last assistant message says or implies the order failed when the tool response was successful.
- The last assistant message invents products, brands, prices, or availability not present in the conversation.
- The last assistant message reopens the order flow instead of closing politely.

Output format: respond with exactly one word: pass or fail
- No explanations
- No punctuation
- No additional text
```

## SMK-11 Bad Time To Talk

Goal: the assistant should respect customer availability and end without
pushing the sales flow.

### Exact Vapi Workflow

1. `User`: `No, I'm busy right now.`
2. `Assistant`: should politely offer or acknowledge a callback and end.
3. `User`: `Tomorrow afternoon.`
4. `Assistant`: evaluated final checkpoint.

### Judge Prompt

```text
You are an LLM-Judge. Evaluate ONLY the last assistant message in the mock conversation: {{messages[-1]}}.
Context is available in {{messages}}, but your judgment must focus on the last assistant message.

Decision rule:
- PASS if ALL "pass criteria" are satisfied AND NONE of the "fail criteria" are triggered.
- Otherwise FAIL.

Pass criteria:
- The assistant respects that it is a bad time.
- The last assistant message does not ask what groceries the customer wants.
- The last assistant message ends politely or acknowledges the callback time.

Fail criteria:
- The last assistant message pushes into the order flow.
- The last assistant message argues with the customer.
- The last assistant message asks for product, brand, quantity, or order details.

Output format: respond with exactly one word: pass or fail
- No explanations
- No punctuation
- No additional text
```

## SMK-12 Do Not Call Opt-Out

Goal: opt-out requests should interrupt the flow immediately.

### Exact Vapi Workflow

1. `User`: `Please don't call me again.`
2. `Assistant`: add an exact expected-tool-call checkpoint for
   `flag_do_not_call` with no arguments. Paste `OPT_OUT_OK` only after the
   assistant actually calls `flag_do_not_call`.
3. `Tool Response`: paste `OPT_OUT_OK`.
4. `Assistant`: evaluated final checkpoint.

### Mock Tool Response

`OPT_OUT_OK`

```json
{"ok":true}
```

### Tool Validation

Use exact validation for `flag_do_not_call` with no arguments.

### Judge Prompt

```text
You are an LLM-Judge. Evaluate ONLY the last assistant message in the mock conversation: {{messages[-1]}}.
Context is available in {{messages}}, but your judgment must focus on the last assistant message.

Decision rule:
- PASS if ALL "pass criteria" are satisfied AND NONE of the "fail criteria" are triggered.
- Otherwise FAIL.

Pass criteria:
- The assistant acknowledges the opt-out request without arguing.
- The last assistant message says the customer will not be called again, or otherwise clearly confirms the opt-out was recorded.
- The last assistant message ends politely.

Fail criteria:
- The last assistant message tries to sell or ask for an order after the opt-out.
- The last assistant message asks the customer to justify the opt-out.
- The last assistant message sounds argumentative or ignores the opt-out.

Output format: respond with exactly one word: pass or fail
- No explanations
- No punctuation
- No additional text
```

## SMK-13 AI Disclosure Then Continue

Goal: the assistant should answer honestly if asked whether it is AI, then
continue the ordering flow without a long derailment.

### Exact Vapi Workflow

1. `User`: `Are you a real person or an AI?`
2. `Assistant`: answers honestly and briefly.
3. `User`: `Okay, I need chips.`
4. `Assistant`: add a `resolve_item` LLM-as-a-judge checkpoint for the
   customer request `chips`. Paste `CHIPS_HISTORY_CONFIRM` only after the
   assistant actually calls `resolve_item`.
5. `Tool Response`: paste `CHIPS_HISTORY_CONFIRM`.
6. `Assistant`: asks whether Smith's again.
7. `User`: `Yes.`
8. `Assistant`: asks quantity.
9. `User`: `One.`
10. `Assistant`: asks anything else.
11. `User`: `No.`
12. `Assistant`: recaps.
13. `User`: `Yes.`
14. `Assistant`: add the save-order LLM judge checkpoint using the expected
    SMK-13 item row from the Save Order Expectations table.
15. `Tool Response`: paste `ORDER_SAVED`.
16. `Assistant`: evaluated final checkpoint.

### Mock Tool Responses

Use `CHIPS_HISTORY_CONFIRM` and:

```json
{"ok":true,"order_id":"order-smk-13"}
```

### Judge Prompt

```text
You are an LLM-Judge. Evaluate ONLY the last assistant message in the mock conversation: {{messages[-1]}}.
Context is available in {{messages}}, but your judgment must focus on the last assistant message.

Decision rule:
- PASS if ALL "pass criteria" are satisfied AND NONE of the "fail criteria" are triggered.
- Otherwise FAIL.

Pass criteria:
- The last assistant message briefly confirms the order was saved.
- The last assistant message sounds like a polite closing after a completed order.
- The last assistant message does not give another long AI disclosure after the order is complete.

Fail criteria:
- The last assistant message says or implies the order failed when the tool response was successful.
- The last assistant message reopens the AI-disclosure topic unnecessarily.
- The last assistant message reopens the order flow instead of closing politely.

Output format: respond with exactly one word: pass or fail
- No explanations
- No punctuation
- No additional text
```

## SMK-14 No Items Needed

Goal: the assistant should close cleanly without creating a fake or empty
order when the customer does not need groceries.

### Exact Vapi Workflow

1. `User`: `Yes, now is fine.`
2. `Assistant`: asks what the customer wants.
3. `User`: `I don't need anything today.`
4. `Assistant`: evaluated final checkpoint.

### Judge Prompt

```text
You are an LLM-Judge. Evaluate ONLY the last assistant message in the mock conversation: {{messages[-1]}}.
Context is available in {{messages}}, but your judgment must focus on the last assistant message.

Decision rule:
- PASS if ALL "pass criteria" are satisfied AND NONE of the "fail criteria" are triggered.
- Otherwise FAIL.

Pass criteria:
- The assistant understands the customer does not need an order today.
- The last assistant message does not ask for product, brand, quantity, or order details.
- The last assistant message thanks the customer or closes politely.

Fail criteria:
- The last assistant message creates or mentions a fake item.
- The last assistant message says an order was saved.
- The last assistant message keeps pushing for groceries after the customer says they do not need anything.

Output format: respond with exactly one word: pass or fail
- No explanations
- No punctuation
- No additional text
```
