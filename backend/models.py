"""Pydantic models shared across routes."""
from datetime import datetime, timezone
from typing import List, Optional, Literal
import uuid
from pydantic import BaseModel, EmailStr, Field, ConfigDict


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


# --- Users ---
class UserPublic(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    email: str
    name: str
    role: Literal["admin", "user"]
    active: bool = True
    avatar_url: Optional[str] = None
    created_at: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    name: str = Field(min_length=1, max_length=80)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AdminCreateUserRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    name: str = Field(min_length=1, max_length=80)
    role: Literal["admin", "user"] = "user"


class AdminUpdateUserRequest(BaseModel):
    name: Optional[str] = None
    role: Optional[Literal["admin", "user"]] = None
    active: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=6, max_length=128)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=6, max_length=128)


class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None
    avatar_url: Optional[str] = None


# --- Channels ---
class ChannelCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    description: str = Field(default="", max_length=200)
    is_private: bool = False


class ChannelUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=40)
    description: Optional[str] = None
    is_private: Optional[bool] = None
    archived: Optional[bool] = None


class ChannelMembersRequest(BaseModel):
    user_ids: List[str]


class ChannelPublic(BaseModel):
    id: str
    name: str
    description: str
    is_private: bool
    archived: bool
    created_by: str
    members: List[str]
    created_at: str


# --- Messages ---
class Attachment(BaseModel):
    type: Literal["image", "gif"]
    url: str
    width: Optional[int] = None
    height: Optional[int] = None
    source: Optional[str] = None  # e.g., "upload", "giphy"


class MessageCreateRequest(BaseModel):
    content: str = Field(default="", max_length=4000)
    attachments: List[Attachment] = Field(default_factory=list)


class MessagePublic(BaseModel):
    id: str
    channel_id: str
    user_id: str
    user_name: str
    user_email: str
    avatar_url: Optional[str] = None
    content: str
    attachments: List[Attachment] = Field(default_factory=list)
    hidden: bool = False
    hidden_by: Optional[str] = None
    hidden_at: Optional[str] = None
    edited_at: Optional[str] = None
    created_at: str
