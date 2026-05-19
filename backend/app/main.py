"""
FastAPI application entry point.

Wires up: DB connect/disconnect via lifespan, CORS for the Next.js frontend,
the feature routers, and a /health endpoint that verifies the DB connection.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import db
from app.config import settings
from app.routers import calls, customers, products


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    await db.connect()
    yield
    # shutdown
    await db.disconnect()


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(products.router)
app.include_router(customers.router)
app.include_router(calls.router)


@app.get("/health", tags=["health"])
async def health():
    """Liveness + DB connectivity check."""
    db_ok = await db.ping()
    return {"status": "ok" if db_ok else "degraded", "database": db_ok}


@app.get("/", tags=["health"])
async def root():
    return {"app": settings.app_name, "docs": "/docs"}
