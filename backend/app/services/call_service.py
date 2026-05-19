"""
Call placement orchestrator.

This is Phase 5: turning a "call this customer" request from the dashboard
into an actual outbound call. The flow:

  1. Load the customer.
  2. Run the compliance gate (services/compliance.py) — DNC + calling hours.
     A blocked call is recorded and returned; it is never dialled.
  3. Place the call via Vapi (services/vapi_client.py), with customer_id in
     the call metadata.
  4. Write a `calls` record so the dashboard can show call state and the
     live-call page can resolve a call_id.

The `calls` collection is the one data-model addition Phase 5 introduces
beyond PROJECT_PLAN section 4. It is created lazily on first insert (the
same way captured_orders was) and stores: who was called, the compliance
decision, the Vapi call id, and status. It is the audit trail for outbound
dialling and the lookup the live-call page needs.

Kept HTTP-free so it can be unit-tested directly.
"""

from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.services import compliance, vapi_client

# call record lifecycle states
STATUS_BLOCKED = "blocked"  # compliance gate refused — not dialled
STATUS_QUEUED = "queued"  # handed to Vapi, call placed
STATUS_FAILED = "failed"  # Vapi rejected the request


def _to_object_id(value: str) -> ObjectId | None:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        return None


async def place_outbound_call(
    db: AsyncIOMotorDatabase,
    customer_id: str,
) -> dict:
    """Place an outbound call to one customer, compliance gate first.

    Args:
        db: the database handle.
        customer_id: the customer's _id as a string.

    Returns:
        A result dict. Shape depends on the outcome:
          - customer missing/invalid:
              { ok: False, error }
          - blocked by compliance:
              { ok: False, blocked: True, compliance: {...}, call_record_id }
          - placed:
              { ok: True, call_id, status, dry_run, compliance: {...},
                call_record_id }
          - Vapi failed:
              { ok: False, error, call_record_id }

    A `calls` record is written for every outcome except an invalid id, so
    the dashboard always has an audit trail.
    """
    oid = _to_object_id(customer_id)
    if oid is None:
        return {"ok": False, "error": "invalid customer_id"}

    customer = await db.customers.find_one({"_id": oid})
    if customer is None:
        return {"ok": False, "error": "customer not found"}

    # --- compliance gate -------------------------------------------------
    gate = compliance.check_customer(customer)
    now = datetime.now(timezone.utc)

    if not gate.allowed:
        # Record the refusal — a blocked call is still an auditable event.
        record = {
            "customer_id": oid,
            "customer_name": customer.get("name", ""),
            "phone": customer.get("phone", ""),
            "created_at": now,
            "status": STATUS_BLOCKED,
            "compliance": gate.to_dict(),
            "vapi_call_id": None,
            "dry_run": vapi_client.is_dry_run(),
            "transcript": [],
        }
        result = await db.calls.insert_one(record)
        return {
            "ok": False,
            "blocked": True,
            "compliance": gate.to_dict(),
            "call_record_id": str(result.inserted_id),
        }

    # --- place the call --------------------------------------------------
    try:
        call = await vapi_client.place_call(
            customer_id=customer_id,
            phone_number=customer.get("phone", ""),
        )
    except vapi_client.VapiError as exc:
        record = {
            "customer_id": oid,
            "customer_name": customer.get("name", ""),
            "phone": customer.get("phone", ""),
            "created_at": now,
            "status": STATUS_FAILED,
            "compliance": gate.to_dict(),
            "vapi_call_id": None,
            "error": str(exc),
            "dry_run": vapi_client.is_dry_run(),
            "transcript": [],
        }
        result = await db.calls.insert_one(record)
        return {
            "ok": False,
            "error": str(exc),
            "call_record_id": str(result.inserted_id),
        }

    # --- success: record the placed call --------------------------------
    record = {
        "customer_id": oid,
        "customer_name": customer.get("name", ""),
        "phone": customer.get("phone", ""),
        "created_at": now,
        "status": STATUS_QUEUED,
        "compliance": gate.to_dict(),
        "vapi_call_id": call["call_id"],
        "dry_run": call["dry_run"],
        "transcript": [],
    }
    result = await db.calls.insert_one(record)
    return {
        "ok": True,
        "call_id": call["call_id"],
        "status": call["status"],
        "dry_run": call["dry_run"],
        "compliance": gate.to_dict(),
        "call_record_id": str(result.inserted_id),
    }


async def get_call(db: AsyncIOMotorDatabase, vapi_call_id: str) -> dict | None:
    """Fetch a call record by its Vapi call id (the id the agent's webhooks
    and the live-call page use). Returns None if not found."""
    doc = await db.calls.find_one({"vapi_call_id": vapi_call_id})
    if doc is None:
        return None

    transcript = doc.get("transcript", [])
    has_assistant_line = any(
        line.get("role") == "assistant"
        for line in transcript
        if isinstance(line, dict)
    )
    should_fetch_transcript = not transcript or not has_assistant_line
    should_fetch_recording = not doc.get("recording_url")

    if (should_fetch_transcript or should_fetch_recording) and not doc.get(
        "dry_run", False
    ):
        try:
            provider_call = await vapi_client.get_call(vapi_call_id)
            update = await update_call_from_provider(db, vapi_call_id, provider_call)
            doc.update(update)
        except vapi_client.VapiError as exc:
            doc["transcript_fetch_error"] = str(exc)

    doc["_id"] = str(doc["_id"])
    doc["customer_id"] = str(doc["customer_id"])
    if doc.get("created_at"):
        doc["created_at"] = doc["created_at"].isoformat()
    doc["transcript"] = doc.get("transcript", [])
    return doc


async def update_call_from_provider(
    db: AsyncIOMotorDatabase, vapi_call_id: str, provider_call: dict
) -> dict:
    """Cache transcript, recording, and status fields from a Vapi call payload."""
    update: dict = {}
    transcript = vapi_client.extract_transcript_lines(provider_call)
    recording_url = vapi_client.extract_recording_url(provider_call)

    if transcript:
        update["transcript"] = transcript
    if recording_url:
        update["recording_url"] = recording_url
    if provider_call.get("status"):
        update["status"] = provider_call["status"]
    if provider_call.get("endedReason"):
        update["ended_reason"] = provider_call["endedReason"]

    if update:
        await db.calls.update_one({"vapi_call_id": vapi_call_id}, {"$set": update})
    return update


async def append_transcript_line(
    db: AsyncIOMotorDatabase, vapi_call_id: str, line: dict
) -> None:
    """Persist a final transcript line on the call record."""
    await db.calls.update_one(
        {"vapi_call_id": vapi_call_id},
        {"$push": {"transcript": line}},
    )


async def list_calls(db: AsyncIOMotorDatabase, limit: int = 50) -> list[dict]:
    """Return recent call records, most recent first — for the dashboard."""
    docs = await db.calls.find().sort("created_at", -1).to_list(length=limit)
    out = []
    for d in docs:
        out.append(
            {
                "_id": str(d["_id"]),
                "customer_id": str(d["customer_id"]),
                "customer_name": d.get("customer_name", ""),
                "phone": d.get("phone", ""),
                "created_at": d["created_at"].isoformat()
                if d.get("created_at")
                else None,
                "status": d.get("status", ""),
                "vapi_call_id": d.get("vapi_call_id"),
                "dry_run": d.get("dry_run", False),
                "compliance": d.get("compliance", {}),
                "transcript_count": len(d.get("transcript", [])),
            }
        )
    return out
