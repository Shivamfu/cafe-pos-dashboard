"""
WebSocket Endpoint for Real-time Floor Plan and KDS live sync.
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.notifier import notifier

router = APIRouter(tags=["WebSocket Realtime"])

@router.websocket("/ws/pos")
async def websocket_pos_endpoint(websocket: WebSocket):
    await notifier.connect(websocket)
    try:
        while True:
            # Keep connection open and accept ping/pong or client action requests
            data = await websocket.receive_text()
            # If client sends ping, respond with pong
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        notifier.disconnect(websocket)
    except Exception:
        notifier.disconnect(websocket)
