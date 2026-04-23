"""Per-user channel unread tracking."""
from datetime import datetime, timezone
from typing import Dict
from fastapi import APIRouter, Depends, HTTPException

from auth import get_current_user
from db import get_db

router = APIRouter(prefix="/channels", tags=["unread"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _get_accessible_channel_ids(db, user: dict) -> list[str]:
    if user.get("role") == "admin":
        docs = await db.channels.find({"archived": {"$ne": True}}, {"_id": 0, "id": 1}).to_list(10000)
    else:
        docs = await db.channels.find(
            {
                "archived": {"$ne": True},
                "$or": [{"is_private": False}, {"members": user["id"]}],
            },
            {"_id": 0, "id": 1},
        ).to_list(10000)
    return [d["id"] for d in docs]


@router.get("/unread")
async def list_unread(user: dict = Depends(get_current_user)) -> Dict[str, int]:
    """Return { channel_id: unread_count } for every accessible channel."""
    db = get_db()
    channel_ids = await _get_accessible_channel_ids(db, user)
    if not channel_ids:
        return {}

    reads = await db.channel_reads.find(
        {"user_id": user["id"], "channel_id": {"$in": channel_ids}}, {"_id": 0}
    ).to_list(len(channel_ids))
    last_read_map = {r["channel_id"]: r["last_read_at"] for r in reads}

    counts: Dict[str, int] = {}
    for cid in channel_ids:
        last_read = last_read_map.get(cid)
        query = {
            "channel_id": cid,
            "hidden": {"$ne": True},
            "user_id": {"$ne": user["id"]},  # own messages don't count
        }
        if last_read:
            query["created_at"] = {"$gt": last_read}
        count = await db.messages.count_documents(query)
        counts[cid] = count
    return counts


@router.post("/{channel_id}/read")
async def mark_read(channel_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    channel = await db.channels.find_one({"id": channel_id}, {"_id": 0})
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    if (
        user.get("role") != "admin"
        and channel.get("is_private")
        and user["id"] not in channel.get("members", [])
    ):
        raise HTTPException(status_code=403, detail="Not a member of this channel")
    now = _now_iso()
    await db.channel_reads.update_one(
        {"user_id": user["id"], "channel_id": channel_id},
        {"$set": {"user_id": user["id"], "channel_id": channel_id, "last_read_at": now}},
        upsert=True,
    )
    return {"ok": True, "last_read_at": now}
