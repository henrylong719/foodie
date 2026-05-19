"""End-to-end SSE test: real server, real HTTP, real streaming.

Boots the FastAPI app with uvicorn, opens an SSE connection to
/calls/{id}/stream, POSTs transcript webhooks, and asserts they arrive on
the stream. This is the test that proves live transcripts actually work.

mongomock is patched in for the DB (the transcript path does not touch it,
but the app's lifespan needs a connection).
"""

import asyncio
import json
import sys
import threading
import time

import httpx
import mongomock
import uvicorn

import app.db as db_module

# --- patch the DB so the app can start without Atlas ---
_mock = mongomock.MongoClient()


async def _fake_connect():
    db_module._state.client = _mock
    db_module._state.db = _mock["test"]


async def _fake_disconnect():
    db_module._state.client = None
    db_module._state.db = None


async def _fake_ping():
    return True


db_module.connect = _fake_connect
db_module.disconnect = _fake_disconnect
db_module.ping = _fake_ping

from app.main import app  # imported after patching

PORT = 8123
BASE = f"http://127.0.0.1:{PORT}"


def _run_server():
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="error")


async def main():
    # boot the server in a background thread
    server_thread = threading.Thread(target=_run_server, daemon=True)
    server_thread.start()

    # wait for it to be ready
    async with httpx.AsyncClient() as client:
        for _ in range(40):
            try:
                r = await client.get(f"{BASE}/health", timeout=1)
                if r.status_code == 200:
                    break
            except Exception:
                pass
            await asyncio.sleep(0.25)
        else:
            print("SERVER DID NOT START")
            sys.exit(1)
        print("  server up           -> /health ok")

        call_id = "call-e2e-1"
        received: list[dict] = []

        # --- open the SSE stream in a background task ---
        async def consume_sse():
            async with httpx.AsyncClient(timeout=None) as sse_client:
                async with sse_client.stream(
                    "GET", f"{BASE}/calls/{call_id}/stream"
                ) as resp:
                    assert resp.status_code == 200
                    ctype = resp.headers.get("content-type", "")
                    assert "text/event-stream" in ctype, f"bad content-type: {ctype}"
                    async for line in resp.aiter_lines():
                        if line.startswith("data: "):
                            received.append(json.loads(line[6:]))
                            if len(received) >= 2:
                                return

        sse_task = asyncio.create_task(consume_sse())
        await asyncio.sleep(0.6)  # let the SSE connection establish

        # --- POST two transcript webhooks, as Vapi would ---
        def transcript(role, text):
            return {
                "message": {
                    "type": "transcript",
                    "transcriptType": "final",
                    "role": role,
                    "transcript": text,
                    "call": {"id": call_id},
                }
            }

        r = await client.post(
            f"{BASE}/calls/webhook",
            json=transcript("assistant", "Hi, anything to order?"),
        )
        assert r.status_code == 200
        await asyncio.sleep(0.15)
        r = await client.post(
            f"{BASE}/calls/webhook", json=transcript("user", "Yes, some chips please")
        )
        assert r.status_code == 200

        # --- wait for the SSE consumer to collect both lines ---
        try:
            await asyncio.wait_for(sse_task, timeout=5)
        except asyncio.TimeoutError:
            print(f"TIMEOUT — only received: {received}")
            sys.exit(1)

        assert len(received) == 2, f"expected 2 lines, got {len(received)}"
        assert received[0]["role"] == "assistant"
        assert received[0]["text"] == "Hi, anything to order?"
        assert received[1]["role"] == "customer", "user -> customer mapping"
        assert received[1]["text"] == "Yes, some chips please"
        print(f"  SSE stream          -> received {len(received)} lines over HTTP")
        print(f"    [1] {received[0]['role']}: {received[0]['text']}")
        print(f"    [2] {received[1]['role']}: {received[1]['text']}")

        # --- a partial transcript must NOT reach the stream ---
        received.clear()
        leftover: list[dict] = []

        async def consume_briefly():
            async with httpx.AsyncClient(timeout=None) as c2:
                async with c2.stream("GET", f"{BASE}/calls/{call_id}/stream") as resp:
                    async for line in resp.aiter_lines():
                        if line.startswith("data: "):
                            leftover.append(json.loads(line[6:]))

        brief = asyncio.create_task(consume_briefly())
        await asyncio.sleep(0.5)
        await client.post(
            f"{BASE}/calls/webhook",
            json={
                "message": {
                    "type": "transcript",
                    "transcriptType": "partial",
                    "role": "user",
                    "transcript": "par...",
                    "call": {"id": call_id},
                }
            },
        )
        await asyncio.sleep(0.6)
        brief.cancel()
        assert leftover == [], "partial transcript leaked to the stream"
        print("  partial over HTTP   -> correctly not streamed")


if __name__ == "__main__":
    asyncio.run(main())
    print("\nALL SSE END-TO-END CHECKS PASSED")
