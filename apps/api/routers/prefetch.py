from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks

from ..core.web_fetch import fetch_and_extract

router = APIRouter()


@router.post("/prefetch")
def prefetch_url(url: str, background_tasks: BackgroundTasks):
    """Prefetch a URL and cache it asynchronously."""

    def _work(u: str):
        fetch_and_extract(u, force=True)

    background_tasks.add_task(_work, url)
    return {"status": "scheduled", "url": url}
