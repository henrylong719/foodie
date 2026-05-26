# Foodie

Foodie is an AI voice-ordering console for a supermarket workflow. The app lets
staff browse customers and catalog items, place outbound ordering calls, review
call history and live transcripts, and inspect captured grocery orders before
fulfillment.

The project is split into a FastAPI backend and a Next.js frontend:

- `backend/` - FastAPI API, MongoDB persistence, Vapi webhook handling, call
  compliance checks, product resolution, customer history, and order capture.
- `frontend/` - Next.js App Router dashboard for customers, calls, orders, and
  catalog review.

## Features

- Staff dashboard with overview metrics for customers, orders, callable contacts,
  and catalog readiness.
- Customer outreach list with do-not-call handling.
- Outbound call placement through Vapi, with dry-run support when no Vapi API key
  is configured.
- Compliance gate for do-not-call status and configured calling hours.
- Live call transcript streaming via Server-Sent Events.
- Product search and item resolution backed by catalog aliases and customer
  purchase history.
- Captured order review pages for checking AI-selected grocery items and brands.
- Seed script for synthetic supermarket data.

## Tech Stack

- Backend: Python 3.12, FastAPI, Motor/PyMongo, Pydantic, uv
- Frontend: Next.js 16, React 19, TypeScript, Tailwind CSS
- Database: MongoDB
- Calling integration: Vapi

## Repository Layout

```text
.
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── routers/
│   │   ├── services/
│   │   └── models/
│   ├── seed.py
│   ├── scripts/test.sh
│   └── pyproject.toml
├── frontend/
│   ├── app/
│   ├── components/
│   ├── lib/
│   └── package.json
└── README.md
```

## Prerequisites

- Python 3.12+
- `uv`
- pnpm
- MongoDB connection string, either local or Atlas
- Optional: Vapi account credentials for real outbound calls

## Environment Setup

Create backend environment settings:

```bash
cd backend
cp .env.example .env
```

Edit `backend/.env` and set at least:

```env
MONGODB_URI=mongodb://localhost:27017
DB_NAME=supermarket_assistant
```

Leave `VAPI_API_KEY` blank to use dry-run mode. In dry-run mode, the compliance
gate still runs and call records are still written, but no real phone call is
placed.

Create frontend environment settings:

```bash
cd frontend
cp .env.example .env.local
```

The default frontend backend URL is:

```env
BACKEND_API_BASE=http://localhost:8000
```

## Install Dependencies

Backend:

```bash
cd backend
uv sync
```

Frontend:

```bash
cd frontend
pnpm install
```

## Seed Data

The seed script creates synthetic products, customers, purchase history, and an
empty captured-orders collection. It wipes and recreates the target collections.

```bash
cd backend
uv run seed.py
```

## Run Locally

Start the backend API:

```bash
cd backend
uv run uvicorn app.main:app --reload
```

Backend URLs:

- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

Start the frontend:

```bash
cd frontend
pnpm dev
```

Frontend URL:

- Dashboard: http://localhost:3000

## Useful Commands

Backend tests:

```bash
cd backend
bash ./scripts/test.sh
```

Frontend lint:

```bash
cd frontend
pnpm lint
```

Frontend build:

```bash
cd frontend
pnpm build
```

## API Overview

Main backend routes:

- `GET /health` - health and database connectivity check
- `GET /products` - browse catalog products
- `GET /products/categories` - list catalog categories
- `GET /products/search?q=...` - resolve a free-text product mention
- `GET /customers` - list customers
- `GET /customers/{customer_id}/history` - get purchase history
- `POST /calls` - place or simulate an outbound call
- `GET /calls` - list call records
- `GET /calls/{call_id}` - get one call record
- `GET /calls/{call_id}/stream` - stream live transcript events
- `POST /calls/webhook` - receive Vapi webhook messages
- `GET /orders` - list captured orders
- `GET /orders/{order_id}` - get one captured order

## Notes

- The frontend proxies API requests through `frontend/app/api` so browser-side
  requests can use `/api/...` while server-side requests use `BACKEND_API_BASE`.
- Backend startup continues in degraded mode if MongoDB is unavailable; check
  `/health` to confirm database connectivity.
- More backend-specific setup details are available in `backend/README.md`.
