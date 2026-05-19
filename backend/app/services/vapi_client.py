"""
Vapi API client — places the actual outbound phone call.

Wraps the one Vapi endpoint this project needs: POST /call/phone, which
starts an outbound call. See https://docs.vapi.ai/calls/outbound-calling.

Two modes:
  - LIVE      — VAPI_API_KEY is set. A real HTTP request is made to Vapi.
  - DRY-RUN   — VAPI_API_KEY is blank. No HTTP happens; a synthetic call id
                is returned so the rest of the flow (compliance gate, call
                record, dashboard redirect) can be demoed without a Vapi
                account. The mode is chosen automatically.

Assistant: the call references a SAVED assistant by id (VAPI_ASSISTANT_ID).
That assistant — its system prompt, voice, the four function tools, and the
server URL pointing at /calls/webhook — is built and configured once in the
Vapi dashboard, following VAPI_AGENT_DESIGN.md. A live call placed without a
configured assistant id is refused with a clear error rather than guessed.

customer_id plumbing: the call is created with `customer_id` set in the
call's `metadata`. Vapi echoes that metadata back on every webhook, which is
exactly what routers/calls.py:_extract_customer_id reads. The voice agent
never sees customer_id — it is backend plumbing end to end.

Kept HTTP-thin and free of FastAPI types so it can be unit-tested by
injecting a fake transport.
"""

from typing import Any

import httpx

from app.config import settings


class VapiError(RuntimeError):
    """Raised when a call cannot be placed — bad config or a Vapi rejection."""


SERVER_MESSAGES = [
    "tool-calls",
    "status-update",
    "transcript",
    "end-of-call-report",
]


def is_dry_run() -> bool:
    """True when no API key is configured — calls are simulated, not placed."""
    return not settings.vapi_api_key


def _build_call_payload(customer_id: str, phone_number: str) -> dict[str, Any]:
    """Assemble the POST /call/phone request body.

    The call references the saved assistant by id. customer_id goes in
    `metadata` (echoed back on every webhook) and is mirrored into
    assistantOverrides.metadata — routers/calls.py checks both locations
    defensively.
    """
    metadata = {"customer_id": customer_id}
    assistant_overrides: dict[str, Any] = {
        "metadata": metadata,
        "serverMessages": SERVER_MESSAGES,
    }
    if settings.vapi_webhook_url:
        assistant_overrides["server"] = {"url": settings.vapi_webhook_url}

    return {
        "assistantId": settings.vapi_assistant_id,
        "phoneNumberId": settings.vapi_phone_number_id,
        "customer": {"number": phone_number},
        "metadata": metadata,
        "assistantOverrides": assistant_overrides,
    }


def _validate_live_config() -> None:
    """Ensure the settings a live call needs are present. Raises VapiError
    listing exactly what is missing."""
    missing = []
    if not settings.vapi_assistant_id:
        missing.append("VAPI_ASSISTANT_ID")
    if not settings.vapi_phone_number_id:
        missing.append("VAPI_PHONE_NUMBER_ID")
    if missing:
        raise VapiError(
            "Cannot place a live call — missing config: "
            + ", ".join(missing)
            + ". Set these in .env, or leave VAPI_API_KEY blank for dry-run."
        )


async def place_call(
    customer_id: str,
    phone_number: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Place an outbound call via Vapi.

    Args:
        customer_id: the customer's _id as a string — goes into call metadata.
        phone_number: the destination number in E.164 form (e.g. +61400…).
        client: optional injected httpx client (tests pass a mock transport).

    Returns:
        { call_id, status, dry_run, provider_status }.
        In dry-run mode call_id is a synthetic "dry-…" id.

    Raises:
        VapiError if live config is incomplete or Vapi rejects the request.
    """
    # --- dry-run: simulate, no telephony ---
    if is_dry_run():
        import uuid

        return {
            "call_id": f"dry-{uuid.uuid4().hex[:16]}",
            "status": "queued",
            "dry_run": True,
            "provider_status": "simulated",
        }

    # --- live: real request to Vapi ---
    _validate_live_config()
    payload = _build_call_payload(customer_id, phone_number)
    headers = {
        "Authorization": f"Bearer {settings.vapi_api_key}",
        "Content-Type": "application/json",
    }
    url = f"{settings.vapi_base_url}/call/phone"

    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=20.0)
    try:
        resp = await client.post(url, json=payload, headers=headers)
    except httpx.HTTPError as exc:
        raise VapiError(f"Could not reach Vapi: {exc}") from exc
    finally:
        if owns_client:
            await client.aclose()

    if resp.status_code not in (200, 201):
        raise VapiError(
            f"Vapi rejected the call ({resp.status_code}): {resp.text[:300]}"
        )

    data = resp.json()
    return {
        "call_id": data.get("id", ""),
        "status": data.get("status", "queued"),
        "dry_run": False,
        "provider_status": data.get("status", ""),
    }


async def get_call(
    call_id: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Fetch a call record from Vapi, including artifacts when available."""
    if is_dry_run():
        return {}

    headers = {"Authorization": f"Bearer {settings.vapi_api_key}"}
    url = f"{settings.vapi_base_url}/call/{call_id}"

    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=20.0)
    try:
        resp = await client.get(url, headers=headers)
    except httpx.HTTPError as exc:
        raise VapiError(f"Could not reach Vapi: {exc}") from exc
    finally:
        if owns_client:
            await client.aclose()

    if resp.status_code != 200:
        raise VapiError(
            f"Vapi rejected call lookup ({resp.status_code}): {resp.text[:300]}"
        )

    return resp.json()


def extract_transcript_lines(call: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize Vapi artifact transcript/messages into dashboard lines."""
    artifact = call.get("artifact") or {}

    raw_lines = artifact.get("transcript")
    if isinstance(raw_lines, list):
        lines = [_normalize_artifact_line(line) for line in raw_lines]
        return [line for line in lines if line is not None]

    raw_lines = artifact.get("messages")
    if isinstance(raw_lines, list):
        lines = [_normalize_artifact_line(line) for line in raw_lines]
        return [line for line in lines if line is not None]

    openai_lines = artifact.get("messagesOpenAIFormatted")
    if isinstance(openai_lines, list):
        lines = [
            _normalize_openai_line(line, index)
            for index, line in enumerate(openai_lines)
        ]
        return [line for line in lines if line is not None]

    return []


def extract_recording_url(call: dict[str, Any]) -> str | None:
    """Return the best recording URL Vapi exposes for a call artifact."""
    artifact = call.get("artifact") or {}

    for key in ("stereoRecordingUrl", "recordingUrl"):
        value = artifact.get(key)
        if isinstance(value, str) and value:
            return value

    recording = artifact.get("recording")
    if isinstance(recording, str) and recording:
        return recording
    if isinstance(recording, dict):
        for key in ("stereoUrl", "url", "monoUrl", "videoUrl"):
            value = recording.get(key)
            if isinstance(value, str) and value:
                return value

    return None


def _normalize_role(role: object) -> str | None:
    if role in ("assistant", "bot"):
        return "assistant"
    if role in ("user", "customer"):
        return "customer"
    return None


def _normalize_artifact_line(line: object) -> dict[str, Any] | None:
    if not isinstance(line, dict):
        return None
    role = _normalize_role(line.get("role"))
    text = line.get("message") or line.get("text") or line.get("transcript")
    if role is None or not isinstance(text, str) or not text.strip():
        return None
    ts = line.get("time") or line.get("secondsFromStart") or line.get("ts") or 0
    return {"role": role, "text": text, "ts": ts}


def _normalize_openai_line(line: object, index: int) -> dict[str, Any] | None:
    if not isinstance(line, dict):
        return None
    role = _normalize_role(line.get("role"))
    text = line.get("content")
    if role is None or not isinstance(text, str) or not text.strip():
        return None
    return {"role": role, "text": text, "ts": index}
