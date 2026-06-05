"""GPU monitoring API routes."""
from fastapi import APIRouter
from services.gpu_monitor import gpu_monitor

router = APIRouter(prefix="/api/gpu", tags=["gpu"])


@router.get("/summary")
async def gpu_summary():
    """Get GPU summary - all GPUs aggregated."""
    return gpu_monitor.get_summary()


@router.get("/metrics")
async def gpu_metrics():
    """Get detailed per-GPU metrics."""
    return {
        "gpus": gpu_monitor.get_metrics(),
        "available": gpu_monitor.is_available(),
    }


@router.get("/history")
async def gpu_history(minutes: int = 10):
    """Get GPU-related alert history."""
    return {
        "events": gpu_monitor.get_history(minutes=minutes),
    }

