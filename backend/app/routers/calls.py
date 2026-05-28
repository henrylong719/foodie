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
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from app.db import get_db
from app.services import call_service, item_resolver, orders
from app.services.event_hub import hub

router = APIRouter(prefix="/calls", tags=["calls"])
logger = logging.getLogger(__name__)


class PlaceCallRequest(BaseModel):
    """Body for POST /calls — the dashboard sends the customer to dial."""

    customer_id: str


async def _resolve_customer_id(
    db: AsyncIOMotorDatabase, call: dict
) -> str | None:
    """Resolve the caller's customer_id.

    Outbound calls: the backend sets customer_id in metadata when placing the
    call, and Vapi echoes it back here. It may appear as call.metadata or
    under assistantOverrides.metadata depending on how the call was created.

    Inbound calls: there is no metadata, so look up the caller's phone number
    (call.customer.number, E.164) in the customers collection.
    """
    if not call:
        return None

    meta = call.get("metadata") or {}
    if meta.get("customer_id"):
        return meta["customer_id"]
    overrides = call.get("assistantOverrides") or {}
    overrides_meta = overrides.get("metadata") or {}
    if overrides_meta.get("customer_id"):
        return overrides_meta["customer_id"]

    customer = call.get("customer") or {}
    number = customer.get("number")
    if not number:
        return None
    record = await db.customers.find_one({"phone": number}, {"_id": 1})
    return str(record["_id"]) if record else None


async def _dispatch(
    db: AsyncIOMotorDatabase,
    name: str,
    args: dict,
    customer_id: str | None,
    call_id: str,
) -> object:
    """Run one tool call and return its result payload."""
    if name == "resolve_item":
        return await item_resolver.resolve_item(
            db, args.get("mention", ""), customer_id or ""
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
        result = await orders.flag_do_not_call(db, customer_id)
        if result.get("ok") and call_id:
            await hub.publish(
                call_id,
                {
                    "role": "assistant",
                    "text": "DNC flagged",
                    "ts": 0,
                    "type": "annotation",
                },
            )
        return result

    return {"error": f"unknown tool: {name}"}


def _as_dict(value: object) -> dict:
    """Normalize tool arguments from Vapi's possible payload shapes."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _extract_tool_call(
    tool_call: dict, tool_meta: dict | None = None
) -> tuple[str, dict]:
    """Return (tool name, args) from current and legacy Vapi tool-call shapes."""
    tool_meta = tool_meta or {}
    function = (
        tool_call.get("function") if isinstance(tool_call.get("function"), dict) else {}
    )
    meta_tool_call = (
        tool_meta.get("toolCall") if isinstance(tool_meta.get("toolCall"), dict) else {}
    )
    meta_function = (
        meta_tool_call.get("function")
        if isinstance(meta_tool_call.get("function"), dict)
        else {}
    )

    name = (
        tool_call.get("name")
        or function.get("name")
        or tool_meta.get("name")
        or meta_function.get("name")
    )

    args = (
        tool_call.get("arguments")
        or tool_call.get("parameters")
        or function.get("arguments")
        or function.get("parameters")
        or meta_tool_call.get("arguments")
        or meta_tool_call.get("parameters")
        or meta_function.get("arguments")
        or meta_function.get("parameters")
    )
    return str(name or ""), _as_dict(args)


def _tool_meta_by_call_id(message: dict) -> dict[str, dict]:
    """Index Vapi's toolWithToolCallList by the nested toolCall id."""
    index = {}
    for item in message.get("toolWithToolCallList", []):
        if not isinstance(item, dict):
            continue
        tool_call = item.get("toolCall")
        if isinstance(tool_call, dict) and tool_call.get("id"):
            index[str(tool_call["id"])] = item
    return index


def _is_transcript_message(msg_type: str) -> bool:
    """Vapi may encode final-only filters in the type string itself."""
    return msg_type == "transcript" or msg_type.startswith("transcript[")


def _extract_transcript_type(message: dict, msg_type: str) -> str:
    """Return Vapi's transcriptType, defaulting to final when omitted."""
    transcript_type = message.get("transcriptType") or message.get("transcript_type")
    if isinstance(transcript_type, str) and transcript_type:
        return transcript_type

    _, bracket, rest = msg_type.partition("[")
    if not bracket:
        return "final"

    attrs, _, _ = rest.partition("]")
    for part in attrs.split(","):
        key, sep, value = part.partition("=")
        if sep and key.strip() == "transcriptType":
            return value.strip().strip("\"'")
    return "final"


def _extract_call_id(message: dict) -> str:
    call = message.get("call") if isinstance(message.get("call"), dict) else {}
    return str(call.get("id") or message.get("callId") or "")


def _summarize_tool_result(result: object) -> object:
    """Keep webhook diagnostics readable while preserving routing clues."""
    if not isinstance(result, dict):
        return result

    fields = (
        "status",
        "ok",
        "error",
        "message",
        "subcategory",
        "available_brands",
        "matched_brand",
        "alternate_subcategory",
        "order_id",
    )
    summary = {field: result[field] for field in fields if field in result}

    product = result.get("product")
    if isinstance(product, dict):
        summary["product"] = {
            key: product[key]
            for key in ("_id", "brand", "name")
            if key in product
        }

    alternate = result.get("alternate_product")
    if isinstance(alternate, dict):
        summary["alternate_product"] = {
            key: alternate[key]
            for key in ("_id", "brand", "name", "subcategory")
            if key in alternate
        }

    return summary


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
    if _is_transcript_message(msg_type):
        call_id = _extract_call_id(message)
        # Vapi defaults transcriptType to "final" when omitted. Forward only
        # final lines — partials get superseded and would flicker the UI.
        if _extract_transcript_type(message, msg_type) == "final":
            role = message.get("role", "")
            # frontend expects "customer"/"assistant"; Vapi sends "user"/"assistant"
            line = {
                "role": "customer" if role == "user" else "assistant",
                "text": message.get("transcript", ""),
                "ts": message.get("timestamp") or 0,
            }
            if call_id and line["text"]:
                await call_service.append_transcript_line(db, call_id, line)
                await hub.publish(call_id, line)
        return {"received": True}

    if msg_type == "status-update":
        call_id = _extract_call_id(message)
        status = message.get("status")
        if call_id and status:
            await call_service.update_call_from_provider(
                db, call_id, {"status": status}
            )
        return {"received": True}

    if msg_type == "end-of-call-report":
        call_id = _extract_call_id(message)
        if call_id:
            provider_call = {
                "artifact": message.get("artifact") or {},
                "status": "ended",
                "endedReason": message.get("endedReason"),
            }
            await call_service.update_call_from_provider(db, call_id, provider_call)
        return {"received": True}

    # Only tool-calls need a meaningful reply; acknowledge anything else.
    if msg_type != "tool-calls":
        return {"received": True}

    call = message.get("call", {})
    call_id = call.get("id", "")
    customer_id = await _resolve_customer_id(db, call)

    results = []
    tool_meta = _tool_meta_by_call_id(message)
    for tool_call in message.get("toolCallList", []):
        if not isinstance(tool_call, dict):
            continue
        name, args = _extract_tool_call(
            tool_call, tool_meta.get(str(tool_call.get("id", "")))
        )
        logger.warning(
            "Vapi tool call received call_id=%s tool_call_id=%s name=%s args=%s",
            call_id,
            tool_call.get("id"),
            name,
            args,
        )
        result = await _dispatch(
            db,
            name,
            args,
            customer_id,
            call_id,
        )
        logger.warning(
            "Vapi tool call result call_id=%s tool_call_id=%s name=%s result=%s",
            call_id,
            tool_call.get("id"),
            name,
            _summarize_tool_result(result),
        )
        results.append(
            {
                "toolCallId": tool_call.get("id"),
                "result": result,
            }
        )

    return {"results": results}


@router.post("")
async def place_call(
    body: PlaceCallRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Place an outbound call to a customer.

    This is Phase 5's entry point. The compliance gate runs first: a
    do-not-call customer or a call outside permitted hours is refused with
    HTTP 409 and a structured reason the dashboard can display. Otherwise
    the call is placed via Vapi (or simulated, in dry-run mode) and the new
    call's id is returned for the live-call view to subscribe to.
    """
    result = await call_service.place_outbound_call(db, body.customer_id)

    # invalid id / unknown customer — a client error
    if not result.get("ok") and not result.get("blocked"):
        if result.get("error") in ("invalid customer_id", "customer not found"):
            raise HTTPException(status_code=404, detail=result["error"])
        # Vapi rejected it or config is incomplete — upstream/config failure
        raise HTTPException(status_code=502, detail=result.get("error", "call failed"))

    # blocked by the compliance gate — 409 Conflict, with the reason
    if result.get("blocked"):
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Call blocked by compliance gate.",
                "compliance": result["compliance"],
            },
        )

    return result


@router.get("")
async def list_calls(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """List recent call records, most recent first."""
    items = await call_service.list_calls(db, limit)
    return {"count": len(items), "calls": items}


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


@router.get("/{vapi_call_id}")
async def get_call(
    vapi_call_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Fetch one call record by its Vapi call id.

    Declared after /{call_id}/stream so the two-segment streaming route is
    matched first; this single-segment route never shadows it.
    """
    doc = await call_service.get_call(db, vapi_call_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Call not found")
    return doc
