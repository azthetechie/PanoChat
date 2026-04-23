"""Messages + moderation."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from auth import get_current_admin, get_current_user
from db import get_db
from models import MessageCreateRequest, MessagePublic, ReactionRequest, new_id, now_iso
from ws_manager import manager

router = APIRouter(prefix="/messages", tags=["messages"])


async def _assert_channel_access(channel_id: str, user: dict) -> dict:
    db = get_db()
    channel = await db.channels.find_one({"id": channel_id}, {"_id": 0})
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    if channel.get("archived") and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Channel is archived")
    if channel.get("is_private") and user.get("role") != "admin":
        if user["id"] not in channel.get("members", []):
            raise HTTPException(status_code=403, detail="Not a member of this channel")
    return channel


def _prepare_message(m: dict, requester: dict) -> dict:
    """Mask hidden content for non-admins."""
    m = dict(m)
    if m.get("hidden") and requester.get("role") != "admin":
        m["content"] = "[message hidden by admin]"
        m["attachments"] = []
    return m


@router.get("/channel/{channel_id}", response_model=List[MessagePublic])
async def list_messages(
    channel_id: str,
    user: dict = Depends(get_current_user),
    limit: int = Query(default=100, ge=1, le=500),
    before: Optional[str] = None,
):
    db = get_db()
    await _assert_channel_access(channel_id, user)
    query = {"channel_id": channel_id}
    if before:
        query["created_at"] = {"$lt": before}
    docs = (
        await db.messages.find(query, {"_id": 0})
        .sort("created_at", -1)
        .limit(limit)
        .to_list(limit)
    )
    docs.reverse()
    return [MessagePublic(**_prepare_message(d, user)) for d in docs]


@router.post("/channel/{channel_id}", response_model=MessagePublic)
async def post_message(
    channel_id: str,
    payload: MessageCreateRequest,
    user: dict = Depends(get_current_user),
):
    db = get_db()
    await _assert_channel_access(channel_id, user)
    if not payload.content.strip() and not payload.attachments:
        raise HTTPException(status_code=400, detail="Empty message")

    doc = {
        "id": new_id(),
        "channel_id": channel_id,
        "user_id": user["id"],
        "user_name": user["name"],
        "user_email": user["email"],
        "avatar_url": user.get("avatar_url"),
        "content": payload.content,
        "attachments": [a.model_dump() for a in payload.attachments],
        "mentions": list({m for m in payload.mentions if m and m != user["id"]}),
        "reactions": {},
        "hidden": False,
        "hidden_by": None,
        "hidden_at": None,
        "edited_at": None,
        "created_at": now_iso(),
    }
    await db.messages.insert_one(dict(doc))
    # Broadcast
    await manager.broadcast_channel(channel_id, {"type": "message:new", "message": doc})
    return MessagePublic(**doc)


@router.post("/{message_id}/react", response_model=MessagePublic)
async def react(
    message_id: str, payload: ReactionRequest, user: dict = Depends(get_current_user)
):
    db = get_db()
    msg = await db.messages.find_one({"id": message_id}, {"_id": 0})
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    # Ensure user has access to the channel
    await _assert_channel_access(msg["channel_id"], user)

    reactions = msg.get("reactions") or {}
    users_for_emoji = list(reactions.get(payload.emoji, []))
    if user["id"] in users_for_emoji:
        users_for_emoji.remove(user["id"])
    else:
        users_for_emoji.append(user["id"])
    if users_for_emoji:
        reactions[payload.emoji] = users_for_emoji
    else:
        reactions.pop(payload.emoji, None)

    await db.messages.update_one({"id": message_id}, {"$set": {"reactions": reactions}})
    msg["reactions"] = reactions
    await manager.broadcast_channel(
        msg["channel_id"], {"type": "message:reactions", "message_id": message_id, "reactions": reactions}
    )
    return MessagePublic(**msg)


@router.post("/{message_id}/hide", response_model=MessagePublic)
async def hide_message(message_id: str, admin: dict = Depends(get_current_admin)):
    db = get_db()
    msg = await db.messages.find_one({"id": message_id}, {"_id": 0})
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    updates = {"hidden": True, "hidden_by": admin["id"], "hidden_at": now_iso()}
    await db.messages.update_one({"id": message_id}, {"$set": updates})
    msg.update(updates)
    await manager.broadcast_channel(
        msg["channel_id"], {"type": "message:hidden", "message_id": message_id}
    )
    return MessagePublic(**msg)


@router.post("/{message_id}/unhide", response_model=MessagePublic)
async def unhide_message(message_id: str, _admin: dict = Depends(get_current_admin)):
    db = get_db()
    msg = await db.messages.find_one({"id": message_id}, {"_id": 0})
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    updates = {"hidden": False, "hidden_by": None, "hidden_at": None}
    await db.messages.update_one({"id": message_id}, {"$set": updates})
    msg.update(updates)
    await manager.broadcast_channel(
        msg["channel_id"], {"type": "message:unhidden", "message": msg}
    )
    return MessagePublic(**msg)


@router.delete("/{message_id}")
async def delete_message(message_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    msg = await db.messages.find_one({"id": message_id}, {"_id": 0})
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    if user["role"] != "admin" and msg["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Cannot delete others' messages")
    await db.messages.delete_one({"id": message_id})
    await manager.broadcast_channel(
        msg["channel_id"], {"type": "message:deleted", "message_id": message_id}
    )
    return {"ok": True}


# --- Admin moderation search ---
class ModerationQuery(BaseModel):
    hidden_only: bool = False
    search: Optional[str] = None
    channel_id: Optional[str] = None


@router.get("/moderation/all", response_model=List[MessagePublic])
async def moderation_list(
    _admin: dict = Depends(get_current_admin),
    hidden_only: bool = Query(default=False),
    search: Optional[str] = Query(default=None),
    channel_id: Optional[str] = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
):
    db = get_db()
    q: dict = {}
    if hidden_only:
        q["hidden"] = True
    if channel_id:
        q["channel_id"] = channel_id
    if search:
        q["content"] = {"$regex": search, "$options": "i"}
    docs = (
        await db.messages.find(q, {"_id": 0})
        .sort("created_at", -1)
        .limit(limit)
        .to_list(limit)
    )
    return [MessagePublic(**d) for d in docs]
