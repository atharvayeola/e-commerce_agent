# CommerceAgent Monorepo

This repository implements a commerce-focused conversational agent spanning:
- FastAPI backend services
- Next.js frontend chat UI
- Offline ingestion/evaluation scripts
- Optional Postgres/pgvector via Docker

It now includes server-side Browse.ai integration, ViT-based image analysis, safer secrets handling, and improved developer ergonomics.

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

Key endpoints (FastAPI):
- GET `/` (root): landing, links to docs
- GET `/healthz`: basic healthcheck
- POST `/recommend`: catalog recommendations with filters
- POST `/agent/chat`: agentic router that supports smalltalk, text recommendations, image search, and optional web/browse sourcing

Run the API locally (quick):

```bash
source agent_env/bin/activate  # or create your own venv
pip install -r apps/api/requirements.txt
export PYTHONPATH=apps
uvicorn apps.api.main:app --reload
```
# CommerceAgent Monorepo

This repository bootstraps a commerce-focused conversational agent: a FastAPI backend, a Next.js frontend chat UI, ingestion/eval scripts, and Docker composition for local dev.

This README has been updated to reflect the features added since the initial scaffold/first PR: web fetch + caching, OpenGraph/JSON-LD extraction, a free DuckDuckGo fallback search, a simple LLM summarization adapter hook, a prefetch admin endpoint, and frontend/client wiring to request web content.

---

## What's new since the first PR

- Web fetching & caching: `apps/api/core/web_fetch.py` fetches pages, extracts main text, and saves cached JSON under `data/web_cache/`.
- OpenGraph & JSON-LD extraction: `web_fetch` now extracts `og:*` metadata and `application/ld+json` blocks and maps Product schema fields (brand, images, offers) into returned product-like cards.
- DuckDuckGo HTML fallback search: `apps/api/core/web_search.py` provides a free fallback to find candidate product pages when local catalog search is empty and `allow_web=true`.
- LLM summarization hook: `apps/api/core/llm_adapter.py` adds a lightweight adapter to summarize long page text (optional Hugging Face token support or a mock fallback).
- Domain allowlist + dev override: `WEB_FETCH_ALLOWLIST` and `WEB_FETCH_ALLOW_ALL=1` env vars control which domains the backend will fetch (default is a small allowlist for safety).
- Prefetch admin endpoint: `/admin/prefetch` (FastAPI router) lets you schedule background page fetches and cache them for faster responses.
- Frontend web integration: the chat UI accepts an optional `web_url` and `allow_web` checkbox. The backend will use the web content (when allowed) to enrich recommendations.
- Source badges & links: web-derived product cards include `source: "web"` and `url` and the frontend shows a source badge and links titles to the original page.

---

## Running locally (quick)

Prerequisites:
- Python 3.9+ virtualenv (this repo includes a sample venv `agent_env/` but you can create your own)
- Node 18+ for the Next frontend

Backend (FastAPI):

```bash
# from repo root
python -m venv .venv           # optional: create your venv
source agent_env/bin/activate  # or source .venv/bin/activate
pip install -r apps/api/requirements.txt

# make the `api` package importable
export PYTHONPATH=apps

# start server (development)
uvicorn api.main:app --reload
```

Frontend (Next.js):

```bash
cd apps/web
npm install
export NEXT_PUBLIC_API_BASE="http://localhost:8000"
npm run dev
```

Notes:
- The frontend defaults to `http://localhost:8000` for the API; set `NEXT_PUBLIC_API_BASE` to change it.
- The backend accepts requests from `http://localhost:3000` via CORS for local dev.

---

## Important environment variables (dev/ops)

- `WEB_FETCH_ALLOWLIST` (optional): comma-separated domains allowed for web fetching, e.g. `amazon.com,walmart.com`
- `WEB_FETCH_ALLOW_ALL` (dev override): set to `1` to allow fetching from ALL domains (use only in dev)
- `HF_TOKEN` (optional): token to let `llm_adapter` call a real HF model; otherwise a deterministic mock is used
- `NEXT_PUBLIC_API_BASE` (frontend): base URL of the API, default `http://localhost:8000`
- `BROWSEAI_API_KEY` (backend only): secret for Browse.ai extractor runs; DO NOT expose to frontend
- `NEXT_PUBLIC_BROWSE_AI_EXTRACTOR_ID` (frontend): default extractor id to use (optional)
- `BROWSEAI_DEBUG` (backend, optional): set `1` for verbose adapter logs (requests, polling, cache)

---

## How the agent uses web + browse content

1. When the client sets `allow_web=true` (and optionally provides a `web_url`), the backend will try to fetch and extract page text via `fetch_and_extract()`.
2. The extracted text may be summarized via `llm_adapter.summarize_text()` to keep prompts compact.
3. If the local catalog recommendation returns no results and `allow_web=true`, the agent will run a DuckDuckGo fallback search for candidate pages, fetch them, extract metadata (OG/JSON-LD), convert to product-like cards, and return these to the client.

Returned web-sourced cards include fields: `id`, `title`, `image_urls`, `price_cents`, `currency`, `badges`, `description`/`rationale`, `source`, and `url` to help the frontend present them and attribute origin. Browse.ai-sourced cards are normalized to the same shape with `source: "browseai"`.

What’s new:
- Server-only Browse.ai integration. The frontend no longer sends or stores API keys. Set `BROWSEAI_API_KEY` on the backend; optionally set `NEXT_PUBLIC_BROWSE_AI_EXTRACTOR_ID` on the frontend.
- Added `browse_force` flag to `/agent/chat` to bypass cache and force a fresh Browse.ai run.
- Added `BROWSEAI_DEBUG=1` to surface detailed adapter logs.
- ViT-based image analysis for visual search with `transformers` + `Pillow`.
- Allow-all web fetch for quick prototyping: `WEB_FETCH_ALLOW_ALL=1`.

---

## Manual testing examples

Root:

```bash
curl http://127.0.0.1:8000/
```

Chat (allow web fetch inline):

```bash
curl -X POST http://127.0.0.1:8000/agent/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"fruit blender","allow_web":true}'
```

Chat (with explicit web URL):

```bash
curl -X POST http://127.0.0.1:8000/agent/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"does this fit my needs","web_url":"https://www.example.com/product/123","allow_web":true}'
```

If web-derived products are found, the JSON includes products with `source: "web"` and a `url`. If Browse.ai results are found, they include `source: "browseai"`. The frontend displays a small source badge and links titles to the original page.

Browse.ai (server-side) example:

```bash
curl -X POST http://127.0.0.1:8000/agent/chat \
  -H 'Content-Type: application/json' \
  -d '{
        "message":"wireless earbuds under 100",
        "allow_web": true,
        "browse_extractor": "<YOUR_EXTRACTOR_ID>",
        "browse_force": true
      }'
```

Notes:
- Set `BROWSEAI_API_KEY` in the server environment. The frontend never sends the key.
- A 403 from Browse.ai usually means invalid extractor id, insufficient permissions, or plan limitations.
- With `BROWSEAI_DEBUG=1`, logs include top-level response keys and polling progress.

---

## Tests

Run the backend tests from the repo root with `PYTHONPATH=apps`:

```bash
export PYTHONPATH=apps
source agent_env/bin/activate
pytest -q
```

Current test status (dev machine): 8 passed, 1 warning.

---

## Safety & production notes

- The DuckDuckGo HTML scraping fallback is brittle and intended for prototyping. For production, use a SERP provider (SerpAPI, Bing) with proper API keys and rate-limiting.
- Be careful with `WEB_FETCH_ALLOW_ALL=1` — in production, use `WEB_FETCH_ALLOWLIST` and respect robots.txt. Add rate-limiting and per-domain throttling.
- Never expose `BROWSEAI_API_KEY` to the frontend. Keep secrets in server env or a secret manager. Rotate keys if they were exposed.
- Consider robots.txt checks, rate limits, and per-domain throttling before enabling broad web discovery.

---

## Image search: ViT-based analysis

The image-based search pipeline extracts visual features using a lightweight Vision Transformer and matches against catalog entries.

- Code: `apps/api/core/image_analysis.py`
- Deps: `transformers`, `Pillow` (see `apps/api/requirements.txt`)
- Endpoint: `/agent/chat` with `image_b64` triggers image search
- Behavior: Dominant colors + visual embeddings guide similarity; results include catalog `ProductCard`s with a visual rationale.

## Future improvements (shortlist)

- Integrate a vector DB (pgvector/FAISS) with cross-encoder re-ranking for better local results.
- Replace DuckDuckGo scraping with a robust SERP API.
- Improve page extraction (OG/JSON-LD parsing is implemented but can be expanded for more fields) and add structured product parsing.
- Add an admin UI to manage domain allowlist, prefetch queues, and cached pages.
- Add authentication and secure the `/admin/prefetch` endpoint.

---

## Local pgvector for development

The repo includes a lightweight docker-compose file to run Postgres with the pgvector extension for local testing.

Start Postgres with pgvector:

```bash
cd docker
docker compose -f compose.pgvector.yml up -d
```

This launches a Postgres server on `localhost:5432` with database `commerce` and user/password `postgres`/`postgres`.

Populate embeddings for the sample catalog (requires `sentence-transformers` and `psycopg2`):

```bash
source agent_env/bin/activate
pip install sentence-transformers psycopg2-binary
export PGVECTOR_DSN='postgresql://postgres:postgres@localhost:5432/commerce'
python scripts/compute_embeddings.py
```

Once embeddings are loaded, start the API (make sure `PGVECTOR_DSN` remains exported or set in your service env):

```bash
export PYTHONPATH=apps
uvicorn api.main:app --reload
```

Now `/recommend` will use PGVector to retrieve nearest items for a query. If PGVector is unavailable or the query fails, the system automatically falls back to lexical retrieval.
