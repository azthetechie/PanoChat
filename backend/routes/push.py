"""Web-push subscription routes."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_current_user
from db import get_db
from models import now_iso
import push_service

router = APIRouter(prefix="/push", tags=["push"])


class PushKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubscribeRequest(BaseModel):
    endpoint: str
    keys: PushKeys
    expirationTime: Optional[int] = None


@router.get("/vapid-public-key")
async def get_vapid_public_key():
    return {"public_key": push_service.get_public_key()}


@router.post("/subscribe")
async def subscribe(payload: PushSubscribeRequest, user: dict = Depends(get_current_user)):
    db = get_db()
    if not payload.endpoint or not payload.keys.p256dh or not payload.keys.auth:
        raise HTTPException(status_code=400, detail="Invalid subscription")
    doc = {
        "user_id": user["id"],
        "endpoint": payload.endpoint,
        "p256dh": payload.keys.p256dh,
        "auth": payload.keys.auth,
        "created_at": now_iso(),
    }
    await db.push_subscriptions.update_one(
        {"endpoint": payload.endpoint},
        {"$set": doc},
        upsert=True,
    )
    return {"ok": True}


class PushUnsubscribeRequest(BaseModel):
    endpoint: str


@router.post("/unsubscribe")
async def unsubscribe(payload: PushUnsubscribeRequest, user: dict = Depends(get_current_user)):
    db = get_db()
    await db.push_subscriptions.delete_one(
        {"endpoint": payload.endpoint, "user_id": user["id"]}
    )
    return {"ok": True}


@router.post("/test")
async def push_test(user: dict = Depends(get_current_user)):
    """Send a test push to the current user (useful for Profile page UI)."""
    await push_service.send_to_user(
        user["id"],
        {
            "title": "Panorama Comms",
            "body": "Web-push is working! You'll get notified when the tab is closed.",
            "url": "/",
        },
    )
    return {"ok": True}
