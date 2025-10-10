# CommerceAgent Monorepo

An end-to-end, demo-friendly commerce agent:
- FastAPI backend (catalog search, image search, agent router)
- Next.js frontend (chat UI, filters, product grid)
- Lightweight scripts for ingestion/eval
- Containerized deploys (Render + Vercel ready)

This README is written for first-time readers. It explains what’s here, how it works, how to run it, the design choices we made, and what’s pending or intentionally out-of-scope (for now).

## TL;DR

- Local catalog: 50 products across 10 categories (electronics, home-appliance, kitchenware, outdoor, fitness, beauty, toys, books, fashion, office)
- Image analysis: optional ViT classifier + captioning, distilled into keywords/categories for ranking
- Web enrichment: built-in web fetcher; Browse.ai adapter available but currently blocked by extractor 403s for the shared IDs
- Frontend: clean chat UI; result cards are currently text-only (we removed thumbnails by request)

## Repository layout

```
apps/
  api/               # FastAPI backend
  web/               # Next.js frontend
scripts/             # Optional helpers (ingest/eval)
data/                # Sample catalog + golden queries
docker/              # Dockerfiles for API & web
docker-compose.yml   # Optional local stack
```

## How it works (high-level)

1) Chat comes in to `/agent/chat` with either text, an image, or both.
2) The agent classifies intent (smalltalk, text_recommendation, image_search).
3a) Text flow → searches the in-memory catalog deterministically (token overlap) and returns ProductCards.
3b) Image flow → analyzes the image (colors, brightness, aspect, optional object labels + caption) and converts to label/category “hints”; these contribute to scoring against the same catalog.
4) Optional web enrichment → if allowed, fetches a page or falls back to a search, extracts OG/JSON-LD into product-like cards. These appear with source badges.

Everything is intentionally simple and deterministic so the demo runs reliably without external services. Each stub can be swapped out later (vector DB, re-ranker, proper SERP/API, etc.).

## Key components

- `apps/api/routers/agent.py` – Orchestrates the chat flow, calling catalog search or image search and optionally web/Browse.ai.
- `apps/api/routers/catalog.py` – Provides `/catalog/search` and `/catalog/image-search` using the demo dataset.
- `apps/api/core/image_analysis.py` – Image analysis helpers: color extraction, brightness, optional ViT labels and BLIP captions; maps to label hints.
- `apps/api/core/web_fetch.py` – Safe web fetcher with allowlist/allow-all, OG + JSON-LD extraction, and product-card shaping.
- `apps/api/core/browseai_adapter.py` – Server-side Browse.ai extractor call + polling (403 observed for shared extractor IDs).
- `apps/web/components/Chat.tsx` – Chat UI; optional web URL input; shows errors clearly.
- `apps/web/components/ProductGrid.tsx` – Product cards grid. Currently text-only (image block removed by design choice).
- `data/sample_products.json` – The catalog: 50 items x 10 categories (each category has 5 items). Each product carries title, brand, category, price, colors, tags, and at least one image URL.

## Running locally

Prereqs: Python 3.9+ and Node 18+

Backend (FastAPI):

```bash
# from repo root
source agent_env/bin/activate  # or your own venv
pip install -r apps/api/requirements.txt
export PYTHONPATH=apps
uvicorn apps.api.main:app --reload
```

Frontend (Next.js):

```bash
cd apps/web
npm install
export NEXT_PUBLIC_API_BASE="http://localhost:8000"
npm run dev
```

Notes:
- CORS is configured to allow `http://localhost:3000` by default. Adjust `CORS_ALLOW_ORIGINS` if needed.
- The chat UI expects the API base via `NEXT_PUBLIC_API_BASE`.

## Configuration

Backend env vars:
- `WEB_FETCH_ALLOWLIST` – Comma-separated allowed domains.
- `WEB_FETCH_ALLOW_ALL` – Set to `1` in dev to allow all domains.
- `BROWSEAI_API_KEY` – Server-only key for Browse.ai. Do not expose to client.
- `ENABLE_IMAGE_CLASSIFIER` – `1` to enable the ViT object labels pipeline.
- `ENABLE_IMAGE_CAPTIONING` – `1` to enable BLIP captioning (default on when transformers available).

Frontend env vars:
- `NEXT_PUBLIC_API_BASE` – API base URL.
- `NEXT_PUBLIC_BROWSE_AI_EXTRACTOR_ID` – Optional default extractor ID to request.

## Product card contract

We return a compact shape the frontend can render consistently:
- id, title, image (optional), price_cents, currency, category
- description (short), badges (e.g., brand), rationale (why it matched)
- source (catalog/web/browseai), url (when web-sourced)

The grid currently hides `image` by design; re-enable it by restoring the `<img>` block in `ProductGrid.tsx`.

## Design choices and what we tried

- Deterministic scoring first: We chose token-overlap and simple heuristics to keep responses stable and debuggable without external dependencies.
- Label-to-hints mapping: Image labels (and caption tokens) get mapped to domain keywords/categories so the same catalog scoring works for text and image.
- Server-side Browse.ai: We moved the key to the server and normalized to our ProductCard shape. However, shared extractor IDs returned 403s in our tests; integration remains in place pending correct credentials.
- Web fetch safety: The allowlist + allow-all toggle provides safe defaults while enabling demos. OG/JSON-LD extraction often yields clean product metadata; we surface price, brand, images when available.
- UI errors by default: We intentionally surface backend errors in the chat so failures aren’t silent.
- Images on/off: We generated deterministic local thumbnails at one point, then rolled back. The grid now renders text-only for cleaner demos without misleading visuals. You can flip this anytime.

Not yet or deferred:
- Vector DB + re-ranking (pgvector/FAISS) – planned; stubs are structured to make this swap straightforward.
- Robust SERP and scraping – DuckDuckGo HTML fallback and basic extraction are demo-only.
- A unified text-to-hints function – considered to align text and image flows; can be introduced behind a flag without changing the public API.
- Classifier model weights in production – enabling ViT/BLIP requires `transformers`; we gate it via env vars to keep cold starts small.

## Known limitations

- Browse.ai: 403s for extractor IDs we didn’t own/authorize; needs proper extractor setup.
- Web fetch brittleness: HTML structure varies; OG/JSON-LD may be missing or incomplete.
- Deterministic scoring: Great for demos; not SOTA relevance. Swap-in a vector index + reranker for quality.

## Deployment notes

- API on Render (Docker): `docker/Dockerfile.api` uses Python 3.11 and binds to `${PORT}`. Set `PYTHONPATH=apps` and CORS envs. Secrets via dashboard.
- Web on Vercel: Set `NEXT_PUBLIC_API_BASE` to your API URL. No server secrets here.

## Try it

Backend health:
```bash
curl http://127.0.0.1:8000/healthz
```

Chat (catalog-only):
```bash
curl -X POST http://127.0.0.1:8000/agent/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"budget trail backpack"}'
```

Chat (image + text):
```bash
# Base64-encode an image and place into image_b64; optional message helps steer results
curl -X POST http://127.0.0.1:8000/agent/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"looks like a smartwatch","image_b64":"<...>"}'
```

Allow web (dev only):
```bash
curl -X POST http://127.0.0.1:8000/agent/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"espresso grinder under 200","allow_web":true}'
```

## Contributing / next steps

- Optional: add `.gitignore` rules for local CSV/metadata dumps you don’t want committed.
- Add a config flag to toggle image rendering in the grid without code changes.
- Introduce a simple `text_to_hints()` helper (mirrors image labels → hints) to align text and image relevance signals.
- Add a tiny smoke test for `/agent/chat` covering the three intents.
