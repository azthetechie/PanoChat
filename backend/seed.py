"""Seed default admin + seed a #general channel on first run."""
import os
from datetime import datetime, timezone

from auth import hash_password, verify_password
from db import get_db
from models import new_id


async def seed_admin_and_defaults() -> None:
    db = get_db()
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@example.com").lower().strip()
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
    admin_name = os.environ.get("ADMIN_NAME", "Administrator")

    existing = await db.users.find_one({"email": admin_email}, {"_id": 0})
    if existing is None:
        admin_id = new_id()
        await db.users.insert_one(
            {
                "id": admin_id,
                "email": admin_email,
                "password_hash": hash_password(admin_password),
                "name": admin_name,
                "role": "admin",
                "active": True,
                "avatar_url": None,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    else:
        admin_id = existing["id"]
        updates = {}
        # Keep password in sync with .env
        if not verify_password(admin_password, existing.get("password_hash", "")):
            updates["password_hash"] = hash_password(admin_password)
        # Always make sure the seed admin is an active admin
        if existing.get("role") != "admin":
            updates["role"] = "admin"
        if not existing.get("active", True):
            updates["active"] = True
        # Don't overwrite the display name on re-seed — the user can edit it via /profile.
        if updates:
            await db.users.update_one({"id": admin_id}, {"$set": updates})

    # Seed a #general channel if no channels exist
    count = await db.channels.count_documents({})
    if count == 0:
        # gather all active user ids (admin at minimum)
        users = await db.users.find({"active": True}, {"_id": 0, "id": 1}).to_list(10000)
        member_ids = [u["id"] for u in users]
        await db.channels.insert_one(
            {
                "id": new_id(),
                "name": "general",
                "description": "Company-wide announcements and general discussion",
                "is_private": False,
                "archived": False,
                "created_by": admin_id,
                "members": member_ids,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
