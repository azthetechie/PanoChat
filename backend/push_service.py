"""Web-Push notification service.

Auto-generates VAPID keys on first boot and persists them in the `config`
collection so the same keys are reused across restarts. Sends push messages
via pywebpush. Subscriptions are stored per user in `push_subscriptions`.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
from typing import Iterable, Optional

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid
from pywebpush import WebPushException, webpush

from db import get_db

logger = logging.getLogger("push")

_CONFIG_KEY = "vapid_keys"
_vapid_private_pem: Optional[str] = None
_vapid_public_b64: Optional[str] = None
_vapid_subject: str = "mailto:admin@example.com"


def _derive_public_b64(vapid: Vapid) -> str:
    raw = vapid.public_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


async def init_vapid_keys() -> None:
    """Load or generate VAPID keys. Must run once at startup."""
    global _vapid_private_pem, _vapid_public_b64, _vapid_subject
    db = get_db()
    doc = await db.config.find_one({"key": _CONFIG_KEY}, {"_id": 0})
    if doc and doc.get("private_pem") and doc.get("public_b64"):
        _vapid_private_pem = doc["private_pem"]
        _vapid_public_b64 = doc["public_b64"]
    else:
        vapid = Vapid()
        vapid.generate_keys()
        private_pem = vapid.private_pem().decode("ascii")
        public_b64 = _derive_public_b64(vapid)
        await db.config.update_one(
            {"key": _CONFIG_KEY},
            {"$set": {"key": _CONFIG_KEY, "private_pem": private_pem, "public_b64": public_b64}},
            upsert=True,
        )
        _vapid_private_pem = private_pem
        _vapid_public_b64 = public_b64
        logger.info("Generated new VAPID keypair for web-push.")

    admin_email = os.environ.get("ADMIN_EMAIL", "").strip()
    if admin_email:
        _vapid_subject = f"mailto:{admin_email}"
    logger.info("VAPID keys ready. Public key length=%d", len(_vapid_public_b64 or ""))


def get_public_key() -> str:
    if not _vapid_public_b64:
        raise RuntimeError("VAPID keys not initialized")
    return _vapid_public_b64


def _get_private_pem() -> str:
    if not _vapid_private_pem:
        raise RuntimeError("VAPID keys not initialized")
    return _vapid_private_pem


def _send_one(subscription_info: dict, payload: dict) -> tuple[bool, Optional[int]]:
    """Blocking single-subscription send. Returns (success, status_code)."""
    try:
        webpush(
            subscription_info=subscription_info,
            data=json.dumps(payload),
            vapid_private_key=_get_private_pem(),
            vapid_claims={"sub": _vapid_subject},
            ttl=60 * 60 * 24,  # 24h
        )
        return True, 200
    except WebPushException as e:  # noqa: BLE001
        status = e.response.status_code if e.response is not None else None
        logger.warning("Web-push failed status=%s body=%s", status, getattr(e.response, "text", ""))
        return False, status
    except Exception as e:  # noqa: BLE001
        logger.warning("Web-push unexpected error: %s", e)
        return False, None


async def send_to_user(user_id: str, payload: dict) -> None:
    """Send a push payload to every active subscription for a user.
    Removes subscriptions that return 404/410 (gone)."""
    if not _vapid_private_pem:
        return
    db = get_db()
    subs = await db.push_subscriptions.find({"user_id": user_id}, {"_id": 0}).to_list(50)
    if not subs:
        return

    loop = asyncio.get_event_loop()
    for sub in subs:
        sub_info = {
            "endpoint": sub["endpoint"],
            "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]},
        }
        ok, status = await loop.run_in_executor(None, _send_one, sub_info, payload)
        if not ok and status in (404, 410):
            await db.push_subscriptions.delete_one({"endpoint": sub["endpoint"]})


async def send_to_users(user_ids: Iterable[str], payload: dict) -> None:
    tasks = [send_to_user(uid, payload) for uid in user_ids]
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
