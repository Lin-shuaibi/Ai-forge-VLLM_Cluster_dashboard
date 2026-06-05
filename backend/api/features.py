"""New feature APIs: notifications, audit, marketplace, A/B testing."""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import Response
import asyncio
from typing import List, Optional
import json

from services.notification_service import notification_service
from services.audit_service import audit_service
from services.ab_test_service import ab_test_service

router = APIRouter()

# === Notifications API ===
@router.get("/notifications")
async def get_notifications(unread_only: bool = False, limit: int = 50):
    """Get notifications."""
    # TODO: Query from database
    return {
        "notifications": [],
        "unread_count": await notification_service.get_unread_count()
    }

@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str):
    """Mark notification as read."""
    await notification_service.mark_as_read(notification_id)
    return {"success": True}

@router.get("/notifications/ws")
async def notification_websocket(ws):
    """WebSocket endpoint for real-time notifications."""
    notification_service.register_ws_client(ws)
    try:
        while True:
            # Keep connection alive
            await asyncio.sleep(10)
    except:
        pass
    finally:
        notification_service.unregister_ws_client(ws)

# === Audit Logs API ===
@router.get("/audit/logs")
async def get_audit_logs(
    request: Request,
    user_id: Optional[str] = None,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    limit: int = 100
):
    """Query audit logs."""
    logs = await audit_service.query_logs(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        limit=limit
    )
    return {"logs": logs}

@router.get("/audit/export")
async def export_audit_logs(format: str = "json"):
    """Export audit logs."""
    content = await audit_service.export_logs(format)
    if format == "json":
        return Response(content=content, media_type="application/json")
    else:
        return Response(content=content, media_type="text/csv")

async def use_template(template_id: str):
    """Use a template and increment usage count."""
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return {
        "success": True,
        "template": template,
        "config": template.get("recommended_config", {})
    }

# === A/B Testing API ===
@router.get("/models/{model_id}/versions")
async def list_model_versions(model_id: str, active_only: bool = True):
    """List all versions for a model."""
    versions = ab_test_service.list_versions(model_id, active_only=active_only)
    return {"model_id": model_id, "versions": versions}

@router.post("/models/{model_id}/versions")
async def create_model_version(
    model_id: str,
    version_name: str,
    config: dict,
    traffic_weight: int = 100
):
    """Create a new model version."""
    version_id = ab_test_service.create_version(
        model_id, version_name, config, traffic_weight
    )
    return {"version_id": version_id, "success": True}

@router.get("/models/{model_id}/select-version")
async def select_model_version(model_id: str):
    """Select a version based on traffic weighting (for A/B testing)."""
    version = ab_test_service.get_version(model_id)
    if not version:
        raise HTTPException(status_code=404, detail="No active versions found")
    
    return {
        "model_id": model_id,
        "selected_version": version["version_name"],
        "config": version["config"]
    }

@router.post("/models/{model_id}/versions/{version_name}/record")
async def record_version_metrics(
    model_id: str,
    version_name: str,
    success: bool,
    latency_ms: float
):
    """Record performance metrics for a version."""
    ab_test_service.record_metrics(model_id, version_name, success, latency_ms)
    return {"success": True}

@router.get("/models/{model_id}/best-version")
async def get_best_version(model_id: str):
    """Get the best performing version."""
    version = ab_test_service.get_best_version(model_id)
    if not version:
        raise HTTPException(status_code=404, detail="No versions with metrics")
    
    return {
        "model_id": model_id,
        "best_version": version["version_name"],
        "metrics": version.get("metrics", {})
    }
