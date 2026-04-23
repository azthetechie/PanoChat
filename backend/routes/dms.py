"""Direct messages — 1:1 conversations, a special channel `type: "dm"`."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException

from auth import get_current_user
from db import get_db
from models import DmCreateRequest, DmPublic, new_id, now_iso

router = APIRouter(prefix="/dms", tags=["dms"])


def _dm_key(user_a: str, user_b: str) -> str:
    """Stable key for the DM between two users (sorted)."""
    a, b = sorted([user_a, user_b])
    return f"dm:{a}:{b}"


async def _get_or_create_dm(db, me: dict, other_id: str) -> dict:
    if me["id"] == other_id:
        raise HTTPException(status_code=400, detail="Cannot DM yourself")
    other = await db.users.find_one({"id": other_id}, {"_id": 0})
    if not other:
        raise HTTPException(status_code=404, detail="User not found")
    if not other.get("active", True):
        raise HTTPException(status_code=403, detail="That user is deactivated")

    key = _dm_key(me["id"], other_id)
    channel = await db.channels.find_one({"name": key, "type": "dm"}, {"_id": 0})
    if channel:
        return channel

    new_channel = {
        "id": new_id(),
        "name": key,
        "description": "",
        "is_private": True,
        "archived": False,
        "created_by": me["id"],
        "members": sorted([me["id"], other_id]),
        "type": "dm",
        "created_at": now_iso(),
    }
    from pymongo.errors import DuplicateKeyError  # local import to avoid top-level dep noise

    try:
        await db.channels.insert_one(dict(new_channel))
        return new_channel
    except DuplicateKeyError:
        # Race: another request inserted first. Return the existing.
        existing = await db.channels.find_one({"name": key, "type": "dm"}, {"_id": 0})
        if existing:
            return existing
        raise HTTPException(status_code=500, detail="Could not create DM")


async def _dm_to_public(
    db, dm_channel: dict, me_id: str, last_reads: Optional[dict] = None
) -> Optional[DmPublic]:
    members = dm_channel.get("members", [])
    other_id = next((m for m in members if m != me_id), None)
    if not other_id:
        return None
    other = await db.users.find_one({"id": other_id}, {"_id": 0, "password_hash": 0})
    if not other:
        return None

    # Last message preview
    last = (
        await db.messages.find(
            {"channel_id": dm_channel["id"], "hidden": {"$ne": True}}, {"_id": 0}
        )
        .sort("created_at", -1)
        .limit(1)
        .to_list(1)
    )
    last_preview = None
    last_at = None
    if last:
        m = last[0]
        last_at = m.get("created_at")
        if m.get("content"):
            last_preview = m["content"]
        elif m.get("attachments"):
            last_preview = f"[{m['attachments'][0]['type']}]"

    # Unread count
    last_read = (last_reads or {}).get(dm_channel["id"])
    unread_query = {
        "channel_id": dm_channel["id"],
        "hidden": {"$ne": True},
        "user_id": {"$ne": me_id},
    }
    if last_read:
        unread_query["created_at"] = {"$gt": last_read}
    unread = await db.messages.count_documents(unread_query)

    return DmPublic(
        id=dm_channel["id"],
        other_user_id=other_id,
        other_user_name=other.get("name", other.get("email", "Unknown")),
        other_user_email=other.get("email", ""),
        other_user_avatar=other.get("avatar_url"),
        last_message_preview=last_preview,
        last_message_at=last_at,
        unread=unread,
    )


@router.get("", response_model=List[DmPublic])
async def list_dms(user: dict = Depends(get_current_user)):
    db = get_db()
    channels = await db.channels.find(
        {"type": "dm", "members": user["id"]}, {"_id": 0}
    ).to_list(1000)
    reads = await db.channel_reads.find(
        {"user_id": user["id"], "channel_id": {"$in": [c["id"] for c in channels]}},
        {"_id": 0},
    ).to_list(len(channels) or 1)
    reads_map = {r["channel_id"]: r["last_read_at"] for r in reads}

    out: List[DmPublic] = []
    for c in channels:
        pub = await _dm_to_public(db, c, user["id"], reads_map)
        if pub:
            out.append(pub)
    # Sort by last message (recent first), DMs with no messages at the bottom
    out.sort(key=lambda d: d.last_message_at or "", reverse=True)
    return out


@router.post("", response_model=DmPublic)
async def open_dm(payload: DmCreateRequest, user: dict = Depends(get_current_user)):
    db = get_db()
    channel = await _get_or_create_dm(db, user, payload.user_id)
    pub = await _dm_to_public(db, channel, user["id"])
    if not pub:
        raise HTTPException(status_code=500, detail="Could not build DM payload")
    return pub
