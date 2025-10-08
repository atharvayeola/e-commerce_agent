from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from .routers import agent, catalog, recommend

app = FastAPI(title="Commerce Agent API", version="1.0.0")

# Allow the Next.js dev server to call the API during local development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict[str, str]:
    """Provide a friendly landing response for the API root."""
    return {
        "message": "Commerce Agent API is running. Visit /docs for the OpenAPI UI.",
        "health": "/healthz",
    }


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    """Return an empty response to suppress missing favicon errors in development."""
    return Response(status_code=204)

app.include_router(catalog.router, prefix="/catalog", tags=["catalog"])
app.include_router(recommend.router, prefix="", tags=["recommend"])
app.include_router(agent.router, prefix="/agent", tags=["agent"])


@app.get("/healthz")
def healthcheck() -> dict[str, str]:
    """Basic healthcheck endpoint for orchestration and tests."""
    return {"status": "ok"}