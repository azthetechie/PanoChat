"""GIF search via Giphy + (optional) Tenor."""
import os
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from auth import get_current_user

router = APIRouter(prefix="/giphy", tags=["giphy"])


def _extract_giphy(items):
    out = []
    for g in items:
        images = g.get("images", {})
        fixed = images.get("fixed_height") or images.get("original") or {}
        preview = images.get("fixed_height_small") or fixed
        out.append(
            {
                "id": g.get("id"),
                "title": g.get("title", ""),
                "url": fixed.get("url"),
                "preview_url": preview.get("url") or fixed.get("url"),
                "width": int(fixed.get("width", 0) or 0),
                "height": int(fixed.get("height", 0) or 0),
                "source": "giphy",
            }
        )
    return [g for g in out if g["url"]]


@router.get("/search")
async def search_gifs(
    q: str = Query(..., min_length=1, max_length=80),
    limit: int = Query(default=20, ge=1, le=50),
    _user: dict = Depends(get_current_user),
):
    api_key = os.environ.get("GIPHY_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="GIF search not configured (missing GIPHY_API_KEY)")
    params = {"api_key": api_key, "q": q, "limit": limit, "rating": "pg-13"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get("https://api.giphy.com/v1/gifs/search", params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Giphy error: {e}")
    return {"results": _extract_giphy(data.get("data", []))}


@router.get("/trending")
async def trending(
    limit: int = Query(default=20, ge=1, le=50), _user: dict = Depends(get_current_user)
):
    api_key = os.environ.get("GIPHY_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="GIF search not configured (missing GIPHY_API_KEY)")
    params = {"api_key": api_key, "limit": limit, "rating": "pg-13"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get("https://api.giphy.com/v1/gifs/trending", params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Giphy error: {e}")
    return {"results": _extract_giphy(data.get("data", []))}
