"""Authentication helpers: JWT, bcrypt, dependencies."""
from datetime import datetime, timezone, timedelta
from typing import Optional
import os
import bcrypt
import jwt
from fastapi import HTTPException, Request, WebSocket, status
from motor.motor_asyncio import AsyncIOMotorDatabase

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = 60 * 8  # 8 hours for business chat
REFRESH_TOKEN_DAYS = 7


def get_jwt_secret() -> str:
    return os.environ["JWT_SECRET"]


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_MINUTES),
        "type": "access",
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_DAYS),
        "type": "refresh",
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])


def set_auth_cookies(response, access_token: str, refresh_token: str) -> None:
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=ACCESS_TOKEN_MINUTES * 60,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=REFRESH_TOKEN_DAYS * 24 * 60 * 60,
        path="/",
    )


def clear_auth_cookies(response) -> None:
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")


def sanitize_user(user: dict) -> dict:
    """Remove sensitive/internal fields before returning."""
    if not user:
        return user
    safe = {k: v for k, v in user.items() if k not in ("_id", "password_hash")}
    return safe


async def _extract_token(request: Request) -> Optional[str]:
    token = request.cookies.get("access_token")
    if token:
        return token
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None


async def get_current_user(request: Request) -> dict:
    from db import get_db

    token = await _extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")

    db = get_db()
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if not user.get("active", True):
        raise HTTPException(status_code=403, detail="Account deactivated")
    return user


async def get_current_admin(request: Request) -> dict:
    user = await get_current_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return user


async def authenticate_websocket(websocket: WebSocket, db: AsyncIOMotorDatabase) -> Optional[dict]:
    """Authenticate a websocket connection via cookie or ?token= query param."""
    token = websocket.cookies.get("access_token")
    if not token:
        token = websocket.query_params.get("token")
    if not token:
        return None
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            return None
        user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0})
        if not user or not user.get("active", True):
            return None
        return user
    except jwt.PyJWTError:
        return None


# --- Brute force helpers ---
MAX_FAILED = 5
LOCKOUT_MINUTES = 15


def get_real_ip(request: Request) -> str:
    """Return the real client IP honoring X-Forwarded-For / X-Real-IP."""
    xff = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if xff:
        return xff
    xri = (request.headers.get("x-real-ip") or "").strip()
    if xri:
        return xri
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def brute_force_identifiers(request: Request, email: str) -> list[str]:
    """Return a list of identifiers to track: (ip:email) and (email) as fallback."""
    ip = get_real_ip(request)
    return [f"ip:{ip}:{email}", f"email:{email}"]


async def check_brute_force(db, identifiers: list[str]) -> None:
    for identifier in identifiers:
        entry = await db.login_attempts.find_one({"identifier": identifier}, {"_id": 0})
        if entry and entry.get("locked_until"):
            locked_until = entry["locked_until"]
            if isinstance(locked_until, str):
                locked_until = datetime.fromisoformat(locked_until)
            if locked_until > datetime.now(timezone.utc):
                remaining = int((locked_until - datetime.now(timezone.utc)).total_seconds() / 60) + 1
                raise HTTPException(
                    status_code=429,
                    detail=f"Too many failed attempts. Try again in {remaining} minute(s).",
                )


async def record_failed_login(db, identifiers: list[str]) -> None:
    now = datetime.now(timezone.utc)
    for identifier in identifiers:
        entry = await db.login_attempts.find_one({"identifier": identifier}, {"_id": 0})
        count = (entry.get("count", 0) if entry else 0) + 1
        update = {"identifier": identifier, "count": count, "last_attempt": now.isoformat()}
        if count >= MAX_FAILED:
            update["locked_until"] = (now + timedelta(minutes=LOCKOUT_MINUTES)).isoformat()
            update["count"] = MAX_FAILED  # keep at max so next failure re-locks immediately
        await db.login_attempts.update_one(
            {"identifier": identifier}, {"$set": update}, upsert=True
        )


async def clear_failed_login(db, identifiers: list[str]) -> None:
    await db.login_attempts.delete_many({"identifier": {"$in": identifiers}})
