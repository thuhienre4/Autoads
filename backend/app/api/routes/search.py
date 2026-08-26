import httpx
from fastapi import APIRouter, HTTPException, Query

from app.services.google_search_service import search_google


router = APIRouter()


@router.get("/google")
async def google_search(
    q: str = Query(..., min_length=1, max_length=500),
    max_results: int = Query(10, ge=1, le=10),
):
    try:
        return await search_google(q, max_results=max_results)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        detail = "Google Search API request failed."
        try:
            detail = exc.response.json().get("error", {}).get("message", detail)
        except Exception:
            pass
        raise HTTPException(status_code=exc.response.status_code, detail=detail) from exc
