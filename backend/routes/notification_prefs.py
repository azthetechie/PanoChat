"""Per-user notification preferences (server-side).

Stored on the user document so the backend can gate web-push delivery
during quiet hours / when muted, even when the recipient's tab is closed.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - py<3.9 fallback
    ZoneInfo = None  # type: ignore

from auth import get_current_user
from db import get_db

router = APIRouter(prefix="/me/notifications", tags=["notifications"])

DEFAULT_PREFS: dict = {
    "quiet_hours": {
        "enabled": False,
        "start": "22:00",
        "end": "07:00",
        "timezone": "UTC",
    },
    "mute_until": None,  # ISO string or None
    "push_enabled": True,
}


class QuietHours(BaseModel):
    enabled: bool = False
    start: str = Field("22:00", pattern=r"^\d{2}:\d{2}$")
    end: str = Field("07:00", pattern=r"^\d{2}:\d{2}$")
    timezone: str = "UTC"


class NotificationPrefs(BaseModel):
    quiet_hours: QuietHours = QuietHours()
    mute_until: Optional[str] = None
    push_enabled: bool = True


def _merged(user_doc: dict) -> dict:
    """Merge user prefs over defaults so legacy users get sane values."""
    p = (user_doc or {}).get("notification_prefs") or {}
    out = {**DEFAULT_PREFS}
    if isinstance(p.get("quiet_hours"), dict):
        out["quiet_hours"] = {**DEFAULT_PREFS["quiet_hours"], **p["quiet_hours"]}
    if "mute_until" in p:
        out["mute_until"] = p["mute_until"]
    if "push_enabled" in p:
        out["push_enabled"] = bool(p["push_enabled"])
    return out


@router.get("")
async def get_prefs(user: dict = Depends(get_current_user)):
    return _merged(user)


@router.put("")
async def put_prefs(payload: NotificationPrefs, user: dict = Depends(get_current_user)):
    db = get_db()
    doc = payload.model_dump()
    await db.users.update_one(
        {"id": user["id"]}, {"$set": {"notification_prefs": doc}}
    )
    return doc


# ---------------------------------------------------------------------------
# Helpers used by push_service / message routes
# ---------------------------------------------------------------------------


def _parse_hhmm(s: str) -> int:
    try:
        h, m = s.split(":")
        return (int(h) % 24) * 60 + (int(m) % 60)
    except Exception:  # noqa: BLE001
        return 0


def in_quiet_hours_for_user(user_doc: dict, now: Optional[datetime] = None) -> bool:
    """Return True if the user's local time is currently inside their quiet
    hours window. Uses the user's stored IANA timezone."""
    prefs = _merged(user_doc)
    qh = prefs["quiet_hours"]
    if not qh.get("enabled"):
        return False
    tz_name = qh.get("timezone") or "UTC"
    try:
        tz = ZoneInfo(tz_name) if ZoneInfo else None
    except Exception:  # noqa: BLE001
        tz = None
    now = now or datetime.now()
    if tz is not None:
        local = now.astimezone(tz)
    else:
        local = now
    cur = local.hour * 60 + local.minute
    start = _parse_hhmm(qh.get("start", "22:00"))
    end = _parse_hhmm(qh.get("end", "07:00"))
    if start == end:
        return False
    if start < end:
        return start <= cur < end
    return cur >= start or cur < end


def is_muted_now(user_doc: dict, now: Optional[datetime] = None) -> bool:
    prefs = _merged(user_doc)
    mu = prefs.get("mute_until")
    if not mu:
        return False
    try:
        ts = datetime.fromisoformat(mu.replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return False
    now = now or datetime.now(ts.tzinfo) if ts.tzinfo else datetime.now()
    return ts > now


def push_allowed_for_user(user_doc: dict, now: Optional[datetime] = None) -> bool:
    """Combined gate used by the message broadcast path."""
    prefs = _merged(user_doc)
    if not prefs.get("push_enabled", True):
        return False
    if is_muted_now(user_doc, now):
        return False
    if in_quiet_hours_for_user(user_doc, now):
        return False
    return True
