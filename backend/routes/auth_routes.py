"""Auth routes: register (admin-only), login, logout, me, refresh, password reset."""
import os
import secrets
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from auth import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    set_auth_cookies,
    clear_auth_cookies,
    get_current_user,
    get_current_admin,
    sanitize_user,
    check_brute_force,
    record_failed_login,
    clear_failed_login,
    brute_force_identifiers,
)
from db import get_db
from models import (
    LoginRequest,
    RegisterRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    UpdateProfileRequest,
    UserPublic,
    new_id,
    now_iso,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
async def login(payload: LoginRequest, request: Request, response: Response):
    db = get_db()
    email = payload.email.lower().strip()
    identifiers = brute_force_identifiers(request, email)

    await check_brute_force(db, identifiers)

    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user or not verify_password(payload.password, user.get("password_hash", "")):
        await record_failed_login(db, identifiers)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.get("active", True):
        raise HTTPException(status_code=403, detail="Account deactivated. Contact your admin.")

    await clear_failed_login(db, identifiers)

    access = create_access_token(user["id"], user["email"])
    refresh = create_refresh_token(user["id"])
    set_auth_cookies(response, access, refresh)

    return {"user": sanitize_user(user), "access_token": access}


@router.post("/logout")
async def logout(response: Response, _user=Depends(get_current_user)):
    clear_auth_cookies(response)
    return {"ok": True}


@router.get("/me", response_model=UserPublic)
async def me(user: dict = Depends(get_current_user)):
    return UserPublic(**sanitize_user(user))


@router.post("/refresh")
async def refresh_token_endpoint(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")

    db = get_db()
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0})
    if not user or not user.get("active", True):
        raise HTTPException(status_code=401, detail="User not found")

    access = create_access_token(user["id"], user["email"])
    new_refresh = create_refresh_token(user["id"])
    set_auth_cookies(response, access, new_refresh)
    return {"ok": True}


@router.put("/me", response_model=UserPublic)
async def update_my_profile(
    payload: UpdateProfileRequest, user: dict = Depends(get_current_user)
):
    db = get_db()
    updates = {k: v for k, v in payload.model_dump(exclude_none=True).items()}
    if updates:
        await db.users.update_one({"id": user["id"]}, {"$set": updates})
    fresh = await db.users.find_one({"id": user["id"]}, {"_id": 0})
    return UserPublic(**sanitize_user(fresh))


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=6, max_length=128)


@router.post("/change-password")
async def change_password(payload: ChangePasswordRequest, user: dict = Depends(get_current_user)):
    db = get_db()
    if not verify_password(payload.current_password, user.get("password_hash", "")):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    await db.users.update_one(
        {"id": user["id"]}, {"$set": {"password_hash": hash_password(payload.new_password)}}
    )
    return {"ok": True}


@router.post("/forgot-password")
async def forgot_password(payload: ForgotPasswordRequest):
    """Generate a reset token (logged to server console; wire up email later)."""
    db = get_db()
    email = payload.email.lower().strip()
    user = await db.users.find_one({"email": email}, {"_id": 0})
    # Always return ok (don't leak existence)
    if user:
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        await db.password_reset_tokens.insert_one(
            {
                "token": token,
                "user_id": user["id"],
                "expires_at": expires_at,
                "used": False,
                "created_at": now_iso(),
            }
        )
        frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000")
        print(f"[PASSWORD_RESET] Link for {email}: {frontend_url}/reset-password?token={token}")
    return {"ok": True, "message": "If the email exists, a reset link has been generated."}


@router.post("/reset-password")
async def reset_password(payload: ResetPasswordRequest):
    db = get_db()
    entry = await db.password_reset_tokens.find_one({"token": payload.token}, {"_id": 0})
    if not entry or entry.get("used"):
        raise HTTPException(status_code=400, detail="Invalid or used token")
    expires_at = entry["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Token expired")

    await db.users.update_one(
        {"id": entry["user_id"]},
        {"$set": {"password_hash": hash_password(payload.new_password)}},
    )
    await db.password_reset_tokens.update_one({"token": payload.token}, {"$set": {"used": True}})
    return {"ok": True}


# Admin-only registration of new users (self-registration disabled for business use)
@router.post("/register", response_model=UserPublic)
async def register(payload: RegisterRequest, admin: dict = Depends(get_current_admin)):
    db = get_db()
    email = payload.email.lower().strip()
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    doc = {
        "id": new_id(),
        "email": email,
        "password_hash": hash_password(payload.password),
        "name": payload.name.strip(),
        "role": "user",
        "active": True,
        "avatar_url": None,
        "created_at": now_iso(),
    }
    await db.users.insert_one(doc)
    return UserPublic(**sanitize_user(doc))
