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

Frontend (Next):

```bash
cd apps/web
npm install
NEXT_PUBLIC_API_BASE="http://localhost:8000" npm run dev
```

Notes:
- The frontend defaults to `http://localhost:8000` for the API; set `NEXT_PUBLIC_API_BASE` to change it.
- The backend accepts requests from `http://localhost:3000` via CORS for local dev.

---

## Important environment variables (dev/ops)

- WEB_FETCH_ALLOWLIST (optional): comma-separated domains allowed for web fetching, e.g. `amazon.com,walmart.com`
- WEB_FETCH_ALLOW_ALL (dev override): set to `1` to allow fetching from all domains (use only in dev!)
- HF_TOKEN (optional): Hugging Face token if you want `llm_adapter` to call a real HF model for page summarization; otherwise a deterministic mock summary is used.
- NEXT_PUBLIC_API_BASE: frontend env var to point the Next client at the API server.

---

## How the agent uses web content

1. When the client sets `allow_web=true` (and optionally provides a `web_url`), the backend will try to fetch and extract page text via `fetch_and_extract()`.
2. The extracted text may be summarized via `llm_adapter.summarize_text()` to keep prompts compact.
3. If the local catalog recommendation returns no results and `allow_web=true`, the agent will run a DuckDuckGo fallback search for candidate pages, fetch them, extract metadata (OG/JSON-LD), convert to product-like cards, and return these to the client.

Returned web-sourced cards include fields: `id`, `title`, `image_urls`, `price_cents`, `currency`, `badges`, `description`/`rationale`, `source`, and `url` to help the frontend present them and attribute origin.

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

If web-derived products are found, the JSON response will include products with `source: "web"` and a `url` field. The Next frontend displays a small badge with the source and links the title to the original page.

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
- Be careful with `WEB_FETCH_ALLOW_ALL=1` — enabling it in production could expose your service to scraping arbitrary websites. Use `WEB_FETCH_ALLOWLIST` or admin controls for safety.
- Consider robots.txt checks, rate limits, and per-domain throttling before enabling broad web discovery.

---

## Future improvements (shortlist)

- Integrate a vector DB (pgvector/FAISS) with cross-encoder re-ranking for better local results.
- Replace DuckDuckGo scraping with a robust SERP API.
- Improve page extraction (OG/JSON-LD parsing is implemented but can be expanded for more fields) and add structured product parsing.
- Add an admin UI to manage domain allowlist, prefetch queues, and cached pages.
- Add authentication and secure the `/admin/prefetch` endpoint.

---

If you'd like, I can open a PR description summarizing these changes for reviewers, or add a short CHANGELOG.md capturing the per-commit summary.

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
