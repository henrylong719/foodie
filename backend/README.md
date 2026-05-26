# Backend — AI Phone Call Sales Assistant

FastAPI backend. Async MongoDB (Motor) for the API; sync pymongo for the
one-shot seed script.

## Structure

```
backend/
  app/
    main.py          FastAPI app, lifespan, CORS, router registration, /health
    config.py        Settings from environment / .env
    db.py            Async Mongo client, connect/disconnect, ping
    models/
      schemas.py     Pydantic schemas for all collections
    routers/
      products.py    search_products            (filled in Phase 1)
      customers.py   get_customer_history        (filled in Phase 1)
      calls.py       Vapi webhook, save_order    (filled in Phase 3)
    services/        business logic — resolution, search ranking
  seed.py            synthetic data generator (run once)
  smoke_test.py      boots the app against an in-memory DB
  pyproject.toml     project metadata and dependencies (managed by uv)
  uv.lock            pinned dependency versions (generated; commit it)
  .python-version    pinned Python version
  .env.example
```

Routers stay thin (HTTP only); real logic goes in `services/` so it can be
tested without HTTP.

## Setup

This project uses [uv](https://docs.astral.sh/uv/) for dependency and
environment management.

```bash
uv sync                     # creates .venv, installs all dependencies
cp .env.example .env        # then edit .env with your Atlas URI
```

`uv sync` reads `pyproject.toml`, resolves versions into `uv.lock`, and builds
the virtual environment. No manual venv activation needed — `uv run` handles it.

## Seed the database

```bash
uv run seed.py              # reads MONGODB_URI; wipes and reseeds
```

## Run the API

```bash
uv run uvicorn app.main:app --reload
```

- API:  http://localhost:8000
- Docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

## Test

```bash
uv run smoke_test.py        # boots the app, checks endpoints (no Atlas needed)
```

## Managing dependencies

```bash
uv add <package>            # add a runtime dependency
uv add --dev <package>      # add a dev-only dependency
uv remove <package>         # remove a dependency
```

For production installs, `uv sync --no-dev` skips the dev group (mongomock).

