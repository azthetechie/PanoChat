"""WebSocket connection manager (broadcast per channel + presence)."""
from typing import Dict, Set, Callable, Awaitable, Optional
import json
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        # channel_id -> set of websockets
        self.channel_conns: Dict[str, Set[WebSocket]] = {}
        # websocket -> {user_id, name, channels}
        self.ws_meta: Dict[WebSocket, dict] = {}
        # user_id -> count of live sockets
        self.user_conn_count: Dict[str, int] = {}
        # optional hook fired after a user comes online / goes offline
        self._on_presence_change: Optional[Callable[[str, bool], Awaitable[None]]] = None

    def set_presence_callback(self, cb: Callable[[str, bool], Awaitable[None]]) -> None:
        self._on_presence_change = cb

    async def connect(self, ws: WebSocket, user: dict) -> None:
        await ws.accept()
        uid = user["id"]
        self.ws_meta[ws] = {"user_id": uid, "name": user.get("name"), "channels": set()}
        prev = self.user_conn_count.get(uid, 0)
        self.user_conn_count[uid] = prev + 1
        if prev == 0 and self._on_presence_change:
            await self._on_presence_change(uid, True)

    def subscribe(self, ws: WebSocket, channel_id: str) -> None:
        self.channel_conns.setdefault(channel_id, set()).add(ws)
        if ws in self.ws_meta:
            self.ws_meta[ws]["channels"].add(channel_id)

    def unsubscribe(self, ws: WebSocket, channel_id: str) -> None:
        conns = self.channel_conns.get(channel_id)
        if conns and ws in conns:
            conns.remove(ws)
        if ws in self.ws_meta:
            self.ws_meta[ws]["channels"].discard(channel_id)

    async def disconnect(self, ws: WebSocket) -> None:
        meta = self.ws_meta.pop(ws, None)
        if not meta:
            return
        for cid in list(meta["channels"]):
            conns = self.channel_conns.get(cid)
            if conns and ws in conns:
                conns.remove(ws)
        uid = meta["user_id"]
        cur = self.user_conn_count.get(uid, 0) - 1
        if cur <= 0:
            self.user_conn_count.pop(uid, None)
            if self._on_presence_change:
                await self._on_presence_change(uid, False)
        else:
            self.user_conn_count[uid] = cur

    def is_online(self, user_id: str) -> bool:
        return self.user_conn_count.get(user_id, 0) > 0

    def online_user_ids(self) -> list[str]:
        return list(self.user_conn_count.keys())

    async def broadcast_channel(self, channel_id: str, payload: dict) -> None:
        conns = list(self.channel_conns.get(channel_id, set()))
        if not conns:
            return
        data = json.dumps(payload, default=str)
        dead: list[WebSocket] = []
        for ws in conns:
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(ws)

    async def broadcast_all(self, payload: dict) -> None:
        """Send to every connected socket (for presence updates)."""
        data = json.dumps(payload, default=str)
        dead: list[WebSocket] = []
        for ws in list(self.ws_meta.keys()):
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(ws)


manager = ConnectionManager()


async def _presence_broadcast(user_id: str, online: bool) -> None:
    await manager.broadcast_all(
        {"type": "presence:update", "user_id": user_id, "online": online}
    )


manager.set_presence_callback(_presence_broadcast)
