"""Channel management."""
from typing import List
from fastapi import APIRouter, Depends, HTTPException

from auth import get_current_admin, get_current_user
from db import get_db
from models import (
    ChannelCreateRequest,
    ChannelMembersRequest,
    ChannelPublic,
    ChannelUpdateRequest,
    new_id,
    now_iso,
)

router = APIRouter(prefix="/channels", tags=["channels"])


async def _get_channel_or_404(channel_id: str) -> dict:
    db = get_db()
    channel = await db.channels.find_one({"id": channel_id}, {"_id": 0})
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    return channel


def _user_can_view(channel: dict, user: dict) -> bool:
    if user.get("role") == "admin":
        return True
    if not channel.get("is_private", False):
        return True
    return user["id"] in channel.get("members", [])


@router.get("", response_model=List[ChannelPublic])
async def list_channels(user: dict = Depends(get_current_user)):
    db = get_db()
    base_filter = {"type": {"$ne": "dm"}}  # exclude DMs from the channel list
    if user.get("role") == "admin":
        query = base_filter
    else:
        query = {**base_filter, "$or": [{"is_private": False}, {"members": user["id"]}]}
    channels = await db.channels.find(query, {"_id": 0}).sort("created_at", 1).to_list(1000)
    return [ChannelPublic(**c) for c in channels]


@router.post("", response_model=ChannelPublic)
async def create_channel(payload: ChannelCreateRequest, admin: dict = Depends(get_current_admin)):
    db = get_db()
    name = payload.name.strip().lower().replace(" ", "-")
    if await db.channels.find_one({"name": name}):
        raise HTTPException(status_code=409, detail="Channel name already exists")
    # If public → add all active users; if private → only the creator
    if payload.is_private:
        members = [admin["id"]]
    else:
        users = await db.users.find({"active": True}, {"_id": 0, "id": 1}).to_list(10000)
        members = [u["id"] for u in users]
    doc = {
        "id": new_id(),
        "name": name,
        "description": payload.description,
        "is_private": payload.is_private,
        "archived": False,
        "created_by": admin["id"],
        "members": members,
        "type": "channel",
        "created_at": now_iso(),
    }
    await db.channels.insert_one(doc)
    return ChannelPublic(**doc)


@router.patch("/{channel_id}", response_model=ChannelPublic)
async def update_channel(
    channel_id: str, payload: ChannelUpdateRequest, _admin: dict = Depends(get_current_admin)
):
    db = get_db()
    await _get_channel_or_404(channel_id)
    updates = payload.model_dump(exclude_none=True)
    if "name" in updates:
        updates["name"] = updates["name"].strip().lower().replace(" ", "-")
        existing = await db.channels.find_one({"name": updates["name"], "id": {"$ne": channel_id}})
        if existing:
            raise HTTPException(status_code=409, detail="Channel name already exists")
    if updates:
        await db.channels.update_one({"id": channel_id}, {"$set": updates})
    fresh = await db.channels.find_one({"id": channel_id}, {"_id": 0})
    return ChannelPublic(**fresh)


@router.delete("/{channel_id}")
async def delete_channel(channel_id: str, _admin: dict = Depends(get_current_admin)):
    db = get_db()
    result = await db.channels.delete_one({"id": channel_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Channel not found")
    await db.messages.delete_many({"channel_id": channel_id})
    return {"ok": True}


@router.post("/{channel_id}/members", response_model=ChannelPublic)
async def add_members(
    channel_id: str, payload: ChannelMembersRequest, _admin: dict = Depends(get_current_admin)
):
    db = get_db()
    await _get_channel_or_404(channel_id)
    await db.channels.update_one(
        {"id": channel_id}, {"$addToSet": {"members": {"$each": payload.user_ids}}}
    )
    fresh = await db.channels.find_one({"id": channel_id}, {"_id": 0})
    return ChannelPublic(**fresh)


@router.delete("/{channel_id}/members/{user_id}", response_model=ChannelPublic)
async def remove_member(
    channel_id: str, user_id: str, _admin: dict = Depends(get_current_admin)
):
    db = get_db()
    await _get_channel_or_404(channel_id)
    await db.channels.update_one({"id": channel_id}, {"$pull": {"members": user_id}})
    fresh = await db.channels.find_one({"id": channel_id}, {"_id": 0})
    return ChannelPublic(**fresh)
