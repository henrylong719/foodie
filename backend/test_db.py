"""Test Mongo client deployment options."""

import asyncio

import certifi

from app import db


def run():
    timeout_kwargs = {"connectTimeoutMS": 5000, "serverSelectionTimeoutMS": 5000}

    assert db._client_kwargs("mongodb://localhost:27017") == timeout_kwargs
    print("  local uri       -> no TLS override")

    atlas_kwargs = db._client_kwargs(
        "mongodb+srv://user:pass@cluster.fh1ttjy.mongodb.net/?retryWrites=true"
    )
    assert atlas_kwargs == {
        **timeout_kwargs,
        "tls": True,
        "tlsCAFile": certifi.where(),
    }
    print("  atlas srv uri   -> certifi TLS")

    atlas_direct_kwargs = db._client_kwargs(
        "mongodb://user:pass@ac-22jo3hb-shard-00-00.fh1ttjy.mongodb.net:27017/"
    )
    assert atlas_direct_kwargs == {
        **timeout_kwargs,
        "tls": True,
        "tlsCAFile": certifi.where(),
    }
    print("  atlas host uri  -> certifi TLS")

    asyncio.run(_test_failed_connect_cleans_state())
    print("  failed startup  -> state cleaned")


async def _test_failed_connect_cleans_state():
    original_client = db.AsyncIOMotorClient
    try:
        db.AsyncIOMotorClient = _FailingClient
        try:
            await db.connect()
            raise AssertionError("connect() should re-raise ping failures")
        except RuntimeError as exc:
            assert str(exc) == "ping failed"

        assert db._state.client is None
        assert db._state.db is None
    finally:
        db.AsyncIOMotorClient = original_client


class _FailingClient:
    def __init__(self, uri, **kwargs):
        self.admin = _FailingAdmin()
        self.closed = False

    def close(self):
        self.closed = True


class _FailingAdmin:
    async def command(self, name):
        raise RuntimeError("ping failed")


run()
print("\nALL DB CONFIG CHECKS PASSED")
