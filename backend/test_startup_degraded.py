"""Test that app startup survives an unavailable database."""

from fastapi.testclient import TestClient

import app.db as db_module


async def _failing_connect():
    raise RuntimeError("database unavailable")


async def _fake_disconnect():
    db_module._state.client = None
    db_module._state.db = None


async def _fake_ping():
    return False


db_module.connect = _failing_connect
db_module.disconnect = _fake_disconnect
db_module.ping = _fake_ping

from app.main import app  # imported after patching

with TestClient(app) as client:
    r = client.get("/")
    print("GET /        ->", r.status_code, r.json())
    assert r.status_code == 200

    r = client.get("/health")
    print("GET /health  ->", r.status_code, r.json())
    assert r.status_code == 200
    assert r.json() == {"status": "degraded", "database": False}

print("\nAPP STARTS IN DEGRADED DB MODE — OK")
