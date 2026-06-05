"""Global logs WebSocket and API."""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from services.log_manager import log_manager

router = APIRouter(tags=["logs"])


@router.websocket("/ws/logs/global")
async def global_logs(websocket: WebSocket):
    await websocket.accept()
    queue = log_manager.subscribe("global")
    try:
        while True:
            entry = await queue.get()
            await websocket.send_json(entry)
    except WebSocketDisconnect:
        log_manager.unsubscribe("global", queue)
    except Exception:
        log_manager.unsubscribe("global", queue)


@router.websocket("/ws/logs/download")
async def download_logs(websocket: WebSocket):
    await websocket.accept()
    queue = log_manager.subscribe("download")
    try:
        while True:
            entry = await queue.get()
            await websocket.send_json(entry)
    except WebSocketDisconnect:
        log_manager.unsubscribe("download", queue)
    except Exception:
        log_manager.unsubscribe("download", queue)


@router.get("/api/logs/channels")
async def list_channels():
    return {"channels": log_manager.get_channels()}
