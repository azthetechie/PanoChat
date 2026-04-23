"""WebSocket connection manager (broadcast per channel)."""
from typing import Dict, Set
import json
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        # channel_id -> set of websockets
        self.channel_conns: Dict[str, Set[WebSocket]] = {}
        # websocket -> (user_id, set of channel_ids subscribed)
        self.ws_meta: Dict[WebSocket, dict] = {}

    async def connect(self, ws: WebSocket, user: dict) -> None:
        await ws.accept()
        self.ws_meta[ws] = {"user_id": user["id"], "channels": set()}

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

    def disconnect(self, ws: WebSocket) -> None:
        meta = self.ws_meta.pop(ws, None)
        if not meta:
            return
        for cid in list(meta["channels"]):
            conns = self.channel_conns.get(cid)
            if conns and ws in conns:
                conns.remove(ws)

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
            self.disconnect(ws)


manager = ConnectionManager()
