"""
Call endpoints — the Vapi webhook.

Vapi POSTs a "tool-calls" message when the agent invokes a tool. This router
unwraps that envelope, dispatches each tool call to the right service, and
returns the results array Vapi expects:

    request:  { "message": { "type": "tool-calls",
                              "toolCallList": [ {id, name, arguments}, ... ],
                              "call": { "id": ..., "assistantOverrides"/metadata } } }
    response: { "results": [ { "toolCallId": ..., "result": ... }, ... ] }

customer_id is NOT a tool argument — it is set in call metadata when the
backend places the outbound call, and Vapi echoes it back here.
"""

from fastapi import APIRouter, Depends, Request
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db import get_db
from app.services import item_resolver, orders

router = APIRouter(prefix="/calls", tags=["calls"])


def _extract_customer_id(call: dict) -> str | None:
    """Pull customer_id from call metadata.

    Vapi places metadata set at call-creation time on the call object. It may
    appear as call.metadata or under assistantOverrides.metadata depending on
    how the call was created — check both.
    """
    if not call:
        return None
    meta = call.get("metadata") or {}
    if "customer_id" in meta:
        return meta["customer_id"]
    overrides = call.get("assistantOverrides") or {}
    return (overrides.get("metadata") or {}).get("customer_id")


async def _dispatch(
    db: AsyncIOMotorDatabase,
    name: str,
    args: dict,
    customer_id: str | None,
    call_id: str,
) -> object:
    """Run one tool call and return its result payload."""
    if name == "resolve_item":
        if not customer_id:
            return {"status": "ask", "message": "Missing customer context."}
        return await item_resolver.resolve_item(
            db, args.get("mention", ""), customer_id
        )

    if name == "resolve_brand":
        return await item_resolver.resolve_brand(
            db, args.get("subcategory", ""), args.get("brand", "")
        )

    if name == "save_order":
        if not customer_id:
            return {"ok": False, "error": "Missing customer context."}
        return await orders.save_order(
            db, customer_id, call_id, args.get("items", []), args.get("transcript_url")
        )

    if name == "flag_do_not_call":
        if not customer_id:
            return {"ok": False, "error": "Missing customer context."}
        return await orders.flag_do_not_call(db, customer_id)

    return {"error": f"unknown tool: {name}"}


@router.post("/webhook")
async def vapi_webhook(
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Receive Vapi server messages. Handles the 'tool-calls' type."""
    body = await request.json()
    message = body.get("message", {})

    # Only tool-calls need a meaningful reply; acknowledge anything else.
    if message.get("type") != "tool-calls":
        return {"received": True}

    call = message.get("call", {})
    call_id = call.get("id", "")
    customer_id = _extract_customer_id(call)

    results = []
    for tool_call in message.get("toolCallList", []):
        result = await _dispatch(
            db,
            tool_call.get("name", ""),
            tool_call.get("arguments", {}) or {},
            customer_id,
            call_id,
        )
        results.append(
            {
                "toolCallId": tool_call.get("id"),
                "result": result,
            }
        )

    return {"results": results}
