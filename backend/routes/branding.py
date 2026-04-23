"""Branding: logo, hero image, brand name, tagline — configurable by admins."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_current_admin
from db import get_db

router = APIRouter(prefix="/branding", tags=["branding"])

DEFAULT_BRANDING = {
    "brand_name": "PANORAMA / COMMS",
    "tagline": "Internal comms · v1.0",
    "hero_heading": "Built for business, shipped to your server.",
    "hero_subheading": "Self-hosted, secure chat built for operations. Channels, media, GIFs & admin control — no third-party host.",
    "logo_url": None,
    "hero_image_url": None,
}


class BrandingUpdate(BaseModel):
    brand_name: Optional[str] = None
    tagline: Optional[str] = None
    hero_heading: Optional[str] = None
    hero_subheading: Optional[str] = None
    logo_url: Optional[str] = None
    hero_image_url: Optional[str] = None


async def _load_branding(db) -> dict:
    doc = await db.settings.find_one({"key": "branding"}, {"_id": 0})
    data = {**DEFAULT_BRANDING}
    if doc and isinstance(doc.get("value"), dict):
        for k, v in doc["value"].items():
            if k in data:
                data[k] = v
    return data


@router.get("")
async def get_branding():
    """Public (unauthenticated) so the Login screen can load branding."""
    db = get_db()
    return await _load_branding(db)


@router.put("")
async def update_branding(
    payload: BrandingUpdate, _admin: dict = Depends(get_current_admin)
):
    db = get_db()
    current = await _load_branding(db)
    updates = {k: v for k, v in payload.model_dump(exclude_none=True).items()}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    current.update(updates)
    await db.settings.update_one(
        {"key": "branding"}, {"$set": {"key": "branding", "value": current}}, upsert=True
    )
    return current
