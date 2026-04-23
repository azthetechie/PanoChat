"""Dynamic PWA manifest — respects live branding from the admin dashboard."""
from fastapi import APIRouter, Request

from db import get_db
from routes.branding import _load_branding

router = APIRouter(tags=["pwa"])


def _abs(base: str, path: str) -> str:
    if not path:
        return path
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return f"{base}{path}"


@router.get("/manifest.webmanifest")
async def webmanifest(request: Request):
    db = get_db()
    branding = await _load_branding(db)
    # Absolute base the browser sees (respects ingress host)
    base = str(request.base_url).rstrip("/")
    # The backend is reachable at /api/*. Static frontend assets are at root,
    # served by the SPA. Manifest icons must resolve for the browser, so we
    # prefer static frontend icons at root and fall back to the uploaded logo.
    logo_url = branding.get("logo_url")
    icons = []
    if logo_url:
        icons.append(
            {
                "src": _abs(base, logo_url),
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any",
            }
        )
    # Default static icons (served by the frontend container)
    icons.extend(
        [
            {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {
                "src": "/icon-512-maskable.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "maskable",
            },
        ]
    )

    brand_name = branding.get("brand_name") or "Panorama Comms"
    short = brand_name.split("/")[0].strip() or brand_name
    if len(short) > 12:
        short = short[:12]

    return {
        "name": brand_name,
        "short_name": short,
        "description": branding.get("tagline") or "Self-hosted business chat",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "orientation": "any",
        "background_color": "#000000",
        "theme_color": "#FF5A00",
        "icons": icons,
        "categories": ["business", "productivity", "social"],
    }
