"""Smoke test: boot the FastAPI app and hit its endpoints.

Uses mongomock so no live Atlas is needed. Patches app.db to use an in-memory
client, then drives the app with FastAPI's TestClient (which runs lifespan).
"""

import mongomock
from fastapi.testclient import TestClient

import app.db as db_module

# --- swap the async Motor client for an in-memory mock ---
_mock_client = mongomock.MongoClient()


# mongomock doesn't implement the admin "ping" command; real Atlas does.
# Patch it so the smoke test reflects real-cluster behaviour.
async def _admin_command(cmd, *args, **kwargs):
    return {"ok": 1}


_mock_client.admin.command = _admin_command


async def _fake_connect():
    db_module._state.client = _mock_client
    db_module._state.db = _mock_client["supermarket_assistant"]


async def _fake_disconnect():
    db_module._state.client = None
    db_module._state.db = None


db_module.connect = _fake_connect
db_module.disconnect = _fake_disconnect

from app.main import app  # imported after patching

with TestClient(app) as client:
    r = client.get("/")
    print("GET /        ->", r.status_code, r.json())
    assert r.status_code == 200

    r = client.get("/health")
    print("GET /health  ->", r.status_code, r.json())
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

    r = client.get("/docs")
    print("GET /docs    ->", r.status_code, "(OpenAPI UI served)")
    assert r.status_code == 200

    schema = client.get("/openapi.json").json()
    routes = sorted(schema["paths"].keys())
    print("registered paths:", routes)

print("\nAPP BOOTS, LIFESPAN RUNS, ENDPOINTS RESPOND — OK")
