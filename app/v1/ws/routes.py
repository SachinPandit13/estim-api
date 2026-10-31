from fastapi import APIRouter
from starlette.websockets import WebSocket, WebSocketDisconnect
from app.v1.ws.manager import ws_manager

router = APIRouter(prefix="/ws", tags=["WebSockets"])


@router.websocket("/alerts")
async def websocket_alerts_endpoint(websocket: WebSocket) -> None:
    """Real-time WebSocket endpoint for industrial safety alerts and incident broadcasts."""
    await ws_manager.connect(websocket)
    try:
        # Send initial connection confirmation
        await websocket.send_json({
            "type": "CONNECTION_ESTABLISHED",
            "message": "Connected to Estim real-time safety incident stream",
        })

        # Keep connection open and respond to client heartbeat pings
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)


@router.get("/status")
def get_ws_status():
    """Returns active WebSocket connection count."""
    return {
        "status": "healthy",
        "active_clients": len(ws_manager.active_connections),
    }
