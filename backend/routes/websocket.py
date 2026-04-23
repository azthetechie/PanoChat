"""WebSocket endpoint: real-time messaging."""
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from auth import authenticate_websocket
from db import get_db
from ws_manager import manager

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    db = get_db()
    user = await authenticate_websocket(websocket, db)
    if not user:
        await websocket.close(code=4401)
        return

    await manager.connect(websocket, user)
    try:
        # Send an initial hello
        await websocket.send_text(json.dumps({"type": "hello", "user_id": user["id"]}))
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except Exception:
                continue
            action = data.get("type")
            if action == "subscribe":
                cid = data.get("channel_id")
                if cid:
                    manager.subscribe(websocket, cid)
                    await websocket.send_text(
                        json.dumps({"type": "subscribed", "channel_id": cid})
                    )
            elif action == "unsubscribe":
                cid = data.get("channel_id")
                if cid:
                    manager.unsubscribe(websocket, cid)
            elif action == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
        try:
            await websocket.close()
        except Exception:
            pass
