# Free Deployment Guide

This guide shows how to deploy the API for free on Render and the Next.js web on Vercel (free tiers).

## 1) Deploy FastAPI to Render (free)

1. Commit your code and push to GitHub (done).
2. Create a new Web Service in Render and connect this repo.
3. Use the following settings:
   - Runtime: Python
   - Build Command: `pip install -r apps/api/requirements.txt`
   - Start Command: `uvicorn apps.api.main:app --host 0.0.0.0 --port $PORT`
   - Environment Variables:
     - `PYTHONPATH=apps`
     - `CORS_ALLOW_ORIGINS=https://<your-web-domain>,http://localhost:3000`
     - `BROWSEAI_API_KEY=<your_key>` (optional)
     - `WEB_FETCH_ALLOWLIST=amazon.com,walmart.com,bestbuy.com` (or leave blank)
   - Plan: Free

Note: Heavy scraping or long-running jobs may hit free tier limits.

## 2) Deploy Next.js to Vercel (free)

1. Import the `apps/web` folder in Vercel (monorepo: set Framework/Root to `apps/web`).
2. Environment Variables:
   - `NEXT_PUBLIC_API_BASE=https://<your-render-service-name>.onrender.com`
   - `NEXT_PUBLIC_BROWSE_AI_EXTRACTOR_ID=<optional>`
3. Click Deploy. Vercel will build and host your static + SSR pages.

## 3) Local fallback / Docker
- You can also run with Docker Compose locally (optional): create a simple Dockerfile for the API, or use the provided stubs in `docker/` and tune as needed.

## 4) CORS & security
- Use `CORS_ALLOW_ORIGINS` on the API to restrict origins in production.
- Never expose `BROWSEAI_API_KEY` to the frontend. Keep it only on the API service.

## 5) Troubleshooting
- API returning 403 on Browse.ai: check extractor id and key permissions; plan limits may apply.
- Web fetch blocked or 403: add domains to `WEB_FETCH_ALLOWLIST`, or consider `WEB_FETCH_ALLOW_ALL=1` for dev only.
- CORS errors: verify `CORS_ALLOW_ORIGINS` matches your Vercel domain.
