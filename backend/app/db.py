"""
Async MongoDB connection layer.

Holds a single Motor client for the app's lifetime. Routers and services get
the database handle via get_db(). Connection open/close is wired to FastAPI's
lifespan in main.py.

The seed script uses sync pymongo separately — a one-shot script has no reason
to be async — but points at the same cluster and database.
"""
import certifi
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import settings


class _Database:
    client: AsyncIOMotorClient | None = None
    db: AsyncIOMotorDatabase | None = None


_state = _Database()


async def connect() -> None:
    """Open the client and verify the connection. Called on app startup."""
    _state.client = AsyncIOMotorClient(
        settings.mongodb_uri,
        **_client_kwargs(settings.mongodb_uri),
    )
    try:
        await _state.client.admin.command("ping")
        _state.db = _state.client[settings.db_name]
    except Exception:
        await disconnect()
        raise


async def disconnect() -> None:
    """Close the client. Called on app shutdown."""
    if _state.client is not None:
        _state.client.close()
        _state.client = None
        _state.db = None


def get_db() -> AsyncIOMotorDatabase:
    """Return the database handle. Use as a FastAPI dependency."""
    if _state.db is None:
        raise RuntimeError("Database not connected. Is the app started?")
    return _state.db


async def ping() -> bool:
    """True if the database responds. Used by the /health endpoint."""
    if _state.client is None:
        return False
    try:
        await _state.client.admin.command("ping")
        return True
    except Exception:
        return False


def _client_kwargs(uri: str) -> dict[str, object]:
    """Return connection options that are safe for Atlas but leave local Mongo alone."""
    kwargs: dict[str, object] = {
        "connectTimeoutMS": 5000,
        "serverSelectionTimeoutMS": 5000,
    }
    normalized_uri = uri.lower()
    if normalized_uri.startswith("mongodb+srv://") or ".mongodb.net" in normalized_uri:
        kwargs.update({"tls": True, "tlsCAFile": certifi.where()})
    return kwargs
