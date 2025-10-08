# CommerceAgent Monorepo

This repository bootstraps a commerce-focused conversational agent spanning FastAPI backend services, a Next.js frontend, offline ingestion scripts, and Docker-based infrastructure. It captures the architecture and implementation roadmap described in the project brief so contributors can expand from a working scaffold.

## Overview

- **Agent-first architecture:** A single CommerceAgent LLM orchestrates catalog search, image search, recommendations, and smalltalk.
- **Backend:** FastAPI service exposing `/catalog`, `/recommend`, and `/agent` endpoints with stub logic that can be upgraded to production-grade vector search and reranking.
- **Frontend:** Next.js + Tailwind chat experience with product grid, quick filters, and image upload placeholder.
- **Data:** Sample product catalog and evaluation gold set seeded under `data/`.
- **Tooling:** Ingestion and evaluation CLI stubs, Docker Compose stack with Postgres (pgvector-ready).

## Repository Layout

```
apps/
  api/               # FastAPI application
  web/               # Next.js frontend
scripts/             # CLI utilities for ingestion, embeddings, evaluation
data/                # Sample catalog + evaluation data
docker/              # Container build definitions
docker-compose.yml   # Local development stack
```

## Backend API

The FastAPI service follows the OpenAPI schema defined in the roadmap. Key endpoints:


Run the API locally:

```bash
pip install -r apps/api/requirements.txt
PYTHONPATH=apps uvicorn api.main:app --reload
```
## Manual testing examples

Once the API is running (e.g. with `PYTHONPATH=apps uvicorn api.main:app --reload`), you can test endpoints with curl.

Get root:

```bash
curl http://127.0.0.1:8000/
```

Chat smalltalk example:

```bash
curl -X POST http://127.0.0.1:8000/agent/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "Hi, what's your name?"}'
```

Recommendation example:

```bash
curl -X POST http://127.0.0.1:8000/recommend \
  -H 'Content-Type: application/json' \
  -d '{"goal": "comfortable sandals", "limit": 3}'
```

Catalog search example:

```bash
curl -X POST http://127.0.0.1:8000/catalog/search \
  -H 'Content-Type: application/json' \
  -d '{"query": "sandals", "limit": 4}'
```


## Frontend

The Next.js application implements the chat UI, product grid, and filter chips described in the UX plan. To start the development server:

```bash
cd apps/web
npm install
npm run dev
```

Set `NEXT_PUBLIC_API_BASE` to point at the FastAPI service (defaults to `http://localhost:8000`).

When running the Next dev server locally and the FastAPI backend on port 8000, you can start the frontend like:

```bash
cd apps/web
NEXT_PUBLIC_API_BASE="http://localhost:8000" npm run dev
```

If you prefer to keep the `api` prefix on the client you'll need to mount the backend under `/api` (for example by mounting the FastAPI app behind a proxy or changing `app.include_router(..., prefix="/api")`).

Quick verification (CORS)
--------------------------
If you start the backend and frontend as described, open your browser to the Next app at `http://localhost:3000` and try a chat message. If you see network errors in the browser console, it may be CORS-related; the API now allows requests from `localhost:3000`.

You can also verify with curl (this bypasses browser CORS):

```bash
curl -X POST http://127.0.0.1:8000/agent/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "Hi from the UI test"}'
```


## Docker Compose

Bring up the entire stack with Postgres, API, and web frontend:

```bash
docker compose up --build
```

This launches:

- `db`: Postgres 15 with pgvector extension (via `ankane/pgvector`).
- `api`: FastAPI service served by Uvicorn on `http://localhost:8000`.
- `web`: Next.js app served on `http://localhost:3000`.

## Ingestion & Embeddings

Scripts under `scripts/` document the ingestion pipeline:

- `ingest_catalog.py` — load CSV/JSON, validate, and (stub) ingest.
- `embed_text.py`, `embed_image.py` — placeholder embedding generators to be swapped for real models.
- `eval_text.py`, `eval_image.py` — skeleton evaluation harnesses referencing `data/golden_queries.json`.

## Roadmap Highlights

1. **Scaffolding** — established monorepo structure, Dockerfiles, and baseline schema.
2. **Catalog & Embeddings** — ingestion/embedding CLIs prepared for production implementation.
3. **Search & Recommendation APIs** — endpoints mirror final contracts with deterministic scoring for local testing.
4. **Agent Endpoint** — intent routing stub to be replaced with LLM function-calling logic.
5. **Frontend UX** — chat + product browsing experience with filter chips and image upload placeholder.
6. **Evaluation & Observability** — gold queries and CLI harness to extend with metrics and logging.

## Next Steps

- Replace heuristic search with vector database integration (pgvector/FAISS) and cross-encoder reranking.
- Connect `ImageDropzone` to backend image search by encoding uploads.
- Implement real ingestion to Postgres with Alembic migrations.
- Add authentication, logging, and observability instrumentation per production requirements.