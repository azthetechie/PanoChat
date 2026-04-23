"""Presence — who's online right now (derived from live WS connections)."""
from fastapi import APIRouter, Depends

from auth import get_current_user
from ws_manager import manager

router = APIRouter(prefix="/presence", tags=["presence"])


@router.get("")
async def list_presence(_user: dict = Depends(get_current_user)):
    """Return the set of currently-connected user ids.

    Seed data for the frontend — live updates arrive via WS 'presence:update'.
    """
    return {"online": manager.online_user_ids()}
