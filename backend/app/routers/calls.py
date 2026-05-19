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

import asyncio
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db import get_db
from app.services import item_resolver, orders
from app.services.event_hub import hub

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
    """Receive Vapi server messages. Handles 'tool-calls' and 'transcript'."""
    body = await request.json()
    message = body.get("message", {})
    msg_type = message.get("type", "")

    # --- transcript events: relay final transcripts to live dashboards ---
    if msg_type == "transcript":
        call_id = message.get("call", {}).get("id", "")
        # Vapi defaults transcriptType to "final" when omitted. Forward only
        # final lines — partials get superseded and would flicker the UI.
        if message.get("transcriptType", "final") == "final":
            role = message.get("role", "")
            # frontend expects "customer"/"assistant"; Vapi sends "user"/"assistant"
            line = {
                "role": "customer" if role == "user" else "assistant",
                "text": message.get("transcript", ""),
                "ts": message.get("timestamp") or 0,
            }
            if call_id and line["text"]:
                await hub.publish(call_id, line)
        return {"received": True}

    # Only tool-calls need a meaningful reply; acknowledge anything else.
    if msg_type != "tool-calls":
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


@router.get("/{call_id}/stream")
async def call_transcript_stream(call_id: str):
    """Server-Sent Events stream of live transcript lines for a call.

    The dashboard's live-call page opens an EventSource against this. Each
    transcript line published to the hub is sent as one SSE 'data:' frame.
    A comment ping every 15s keeps the connection from idling out.
    """
    queue = hub.subscribe(call_id)

    async def event_generator():
        try:
            # initial comment so the browser marks the connection open
            yield ": connected\n\n"
            while True:
                try:
                    line = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {json.dumps(line)}\n\n"
                except asyncio.TimeoutError:
                    # keep-alive ping (SSE comment line)
                    yield ": ping\n\n"
        finally:
            hub.unsubscribe(call_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # disable proxy buffering
        },
    )
