"""Admin user management."""
from typing import List
from fastapi import APIRouter, Depends, HTTPException

from auth import get_current_admin, get_current_user, hash_password, sanitize_user
from db import get_db
from models import (
    AdminCreateUserRequest,
    AdminUpdateUserRequest,
    UserPublic,
    new_id,
    now_iso,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=List[UserPublic])
async def list_users(_user: dict = Depends(get_current_user)):
    """Any authenticated user can see the member directory (needed for chat mentions / channel assignment)."""
    db = get_db()
    users = await db.users.find({}, {"_id": 0, "password_hash": 0}).sort("created_at", 1).to_list(1000)
    return [UserPublic(**u) for u in users]


@router.post("", response_model=UserPublic)
async def create_user(payload: AdminCreateUserRequest, _admin: dict = Depends(get_current_admin)):
    db = get_db()
    email = payload.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=409, detail="Email already exists")
    doc = {
        "id": new_id(),
        "email": email,
        "password_hash": hash_password(payload.password),
        "name": payload.name.strip(),
        "role": payload.role,
        "active": True,
        "avatar_url": None,
        "created_at": now_iso(),
    }
    await db.users.insert_one(doc)
    return UserPublic(**sanitize_user(doc))


@router.patch("/{user_id}", response_model=UserPublic)
async def update_user(
    user_id: str, payload: AdminUpdateUserRequest, admin: dict = Depends(get_current_admin)
):
    db = get_db()
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    updates = {}
    data = payload.model_dump(exclude_none=True)
    if "password" in data:
        updates["password_hash"] = hash_password(data.pop("password"))
    updates.update(data)

    # Prevent admin from demoting or deactivating themselves (avoid locking out)
    if user_id == admin["id"]:
        if updates.get("role") and updates["role"] != "admin":
            raise HTTPException(status_code=400, detail="You cannot demote yourself")
        if updates.get("active") is False:
            raise HTTPException(status_code=400, detail="You cannot deactivate yourself")

    if updates:
        await db.users.update_one({"id": user_id}, {"$set": updates})
    fresh = await db.users.find_one({"id": user_id}, {"_id": 0})
    return UserPublic(**sanitize_user(fresh))


@router.delete("/{user_id}")
async def delete_user(user_id: str, admin: dict = Depends(get_current_admin)):
    db = get_db()
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="You cannot delete yourself")
    result = await db.users.delete_one({"id": user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    # Remove from any channels
    await db.channels.update_many({}, {"$pull": {"members": user_id}})
    return {"ok": True}
