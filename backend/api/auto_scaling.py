"""Auto-scaling API."""
import json
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel, Field

from services.auto_scaling_service import (
    auto_scaling_service, ScalingPolicy, AutoScalingService
)
from services.auth_service import get_current_user, require_permission, TokenData

router = APIRouter(prefix="/auto-scaling", tags=["auto-scaling"])


class ScalingPolicyCreate(BaseModel):
    model_name: str = Field(..., description="Model name")
    min_replicas: int = Field(1, ge=1, le=100, description="Minimum replicas")
    max_replicas: int = Field(10, ge=1, le=1000, description="Maximum replicas")
    target_cpu_percent: int = Field(70, ge=1, le=100, description="Target CPU percentage")
    target_memory_percent: int = Field(80, ge=1, le=100, description="Target memory percentage")
    target_qps: int = Field(100, ge=1, description="Target queries per second")
    scale_up_cooldown: int = Field(60, ge=10, description="Scale up cooldown in seconds")
    scale_down_cooldown: int = Field(300, ge=30, description="Scale down cooldown in seconds")
    scale_up_threshold: float = Field(1.2, ge=1.0, le=3.0, description="Scale up threshold multiplier")
    scale_down_threshold: float = Field(0.5, ge=0.1, le=1.0, description="Scale down threshold multiplier")
    scale_up_increment: int = Field(1, ge=1, le=10, description="Scale up increment")
    scale_down_increment: int = Field(1, ge=1, le=10, description="Scale down increment")
    enabled: bool = Field(True, description="Whether policy is enabled")


class MetricsAdd(BaseModel):
    cpu_percent: float = Field(..., ge=0, le=100, description="CPU usage percentage")
    memory_percent: float = Field(..., ge=0, le=100, description="Memory usage percentage")
    requests_per_second: float = Field(..., ge=0, description="Requests per second")
    avg_latency_ms: float = Field(..., ge=0, description="Average latency in milliseconds")
    error_rate: float = Field(..., ge=0, le=1, description="Error rate (0-1)")


class ManualScaleRequest(BaseModel):
    target_replicas: int = Field(..., ge=1, le=1000, description="Target number of replicas")
    reason: str = Field("manual", description="Reason for manual scaling")


@router.post("/policies", response_model=dict)
async def create_scaling_policy(
    policy: ScalingPolicyCreate,
    current_user: TokenData = Depends(require_permission("auto_scaling", "create"))
):
    """Create or update a scaling policy."""
    try:
        scaling_policy = ScalingPolicy(
            model_name=policy.model_name,
            min_replicas=policy.min_replicas,
            max_replicas=policy.max_replicas,
            target_cpu_percent=policy.target_cpu_percent,
            target_memory_percent=policy.target_memory_percent,
            target_qps=policy.target_qps,
            scale_up_cooldown=policy.scale_up_cooldown,
            scale_down_cooldown=policy.scale_down_cooldown,
            scale_up_threshold=policy.scale_up_threshold,
            scale_down_threshold=policy.scale_down_threshold,
            scale_up_increment=policy.scale_up_increment,
            scale_down_increment=policy.scale_down_increment,
            enabled=policy.enabled
        )

        result = auto_scaling_service.set_policy(scaling_policy)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create policy: {str(e)}")


@router.get("/policies/{model_name}", response_model=dict)
async def get_scaling_policy(
    model_name: str,
    current_user: TokenData = Depends(require_permission("auto_scaling", "read"))
):
    """Get scaling policy for a model."""
    try:
        policy = auto_scaling_service.get_policy(model_name)
        if not policy:
            raise HTTPException(status_code=404, detail=f"No policy found for model {model_name}")
        return policy
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get policy: {str(e)}")


@router.delete("/policies/{model_name}", response_model=dict)
async def delete_scaling_policy(
    model_name: str,
    current_user: TokenData = Depends(require_permission("auto_scaling", "delete"))
):
    """Delete a scaling policy."""
    try:
        success = auto_scaling_service.delete_policy(model_name)
        if not success:
            raise HTTPException(status_code=404, detail=f"No policy found for model {model_name}")
        return {"message": f"Policy for {model_name} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete policy: {str(e)}")


@router.get("/policies", response_model=List[dict])
async def list_scaling_policies(
    current_user: TokenData = Depends(require_permission("auto_scaling", "read"))
):
    """List all scaling policies."""
    try:
        # This would need to be implemented in the service
        # For now, return all policies from memory
        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT * FROM scaling_policies ORDER BY model_name")
            rows = c.fetchall()

            policies = []
            for row in rows:
                policy = dict(row)
                policy["enabled"] = bool(policy["enabled"])
                policies.append(policy)

            return policies
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list policies: {str(e)}")


@router.post("/metrics/{model_name}", response_model=dict)
async def add_metrics(
    model_name: str,
    metrics: MetricsAdd,
    current_user: TokenData = Depends(require_permission("auto_scaling", "create"))
):
    """Add metrics for a model."""
    try:
        auto_scaling_service.add_metrics(
            model_name=model_name,
            cpu_percent=metrics.cpu_percent,
            memory_percent=metrics.memory_percent,
            requests_per_second=metrics.requests_per_second,
            avg_latency_ms=metrics.avg_latency_ms,
            error_rate=metrics.error_rate
        )
        return {"message": "Metrics added successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add metrics: {str(e)}")


@router.get("/metrics/{model_name}", response_model=dict)
async def get_metrics(
    model_name: str,
    minutes: int = Query(10, ge=1, le=1440, description="Minutes of metrics to retrieve"),
    current_user: TokenData = Depends(require_permission("auto_scaling", "read"))
):
    """Get metrics for a model."""
    try:
        metrics = auto_scaling_service.get_metrics(model_name, minutes)
        if not metrics:
            raise HTTPException(status_code=404, detail=f"No metrics found for model {model_name}")
        return metrics
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")


@router.post("/scale/{model_name}", response_model=dict)
async def manual_scale(
    model_name: str,
    request: ManualScaleRequest,
    current_user: TokenData = Depends(require_permission("auto_scaling", "update"))
):
    """Manually scale a model."""
    try:
        result = auto_scaling_service.manual_scale(
            model_name=model_name,
            target_replicas=request.target_replicas,
            reason=request.reason
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to scale model: {str(e)}")


@router.get("/history", response_model=List[dict])
async def get_scaling_history(
    model_name: Optional[str] = Query(None, description="Filter by model name"),
    limit: int = Query(50, ge=1, le=1000, description="Maximum number of entries to return"),
    current_user: TokenData = Depends(require_permission("auto_scaling", "read"))
):
    """Get scaling history."""
    try:
        history = auto_scaling_service.get_scaling_history(model_name, limit)
        return history
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get history: {str(e)}")


@router.get("/status", response_model=dict)
async def get_auto_scaling_status(
    current_user: TokenData = Depends(require_permission("auto_scaling", "read"))
):
    """Get auto-scaling system status."""
    try:
        status = auto_scaling_service.get_status()
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")


@router.post("/start", response_model=dict)
async def start_auto_scaling(
    current_user: TokenData = Depends(require_permission("auto_scaling", "update"))
):
    """Start the auto-scaling monitor."""
    try:
        auto_scaling_service.start_monitoring()
        return {"message": "Auto-scaling monitor started"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start monitor: {str(e)}")


@router.post("/stop", response_model=dict)
async def stop_auto_scaling(
    current_user: TokenData = Depends(require_permission("auto_scaling", "update"))
):
    """Stop the auto-scaling monitor."""
    try:
        auto_scaling_service.stop_monitoring()
        return {"message": "Auto-scaling monitor stopped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop monitor: {str(e)}")


@router.get("/recommendations/{model_name}", response_model=List[dict])
async def get_scaling_recommendations(
    model_name: str,
    current_user: TokenData = Depends(require_permission("auto_scaling", "read"))
):
    """Get scaling recommendations for a model."""
    try:
        # Get current metrics
        metrics = auto_scaling_service.get_metrics(model_name, minutes=30)
        policy = auto_scaling_service.get_policy(model_name)

        if not metrics or not policy:
            return []

        recommendations = []

        avg_metrics = metrics.get("average_metrics", {})
        current_replicas = metrics.get("current_replicas", 1)

        # Check CPU
        if avg_metrics.get("cpu_percent", 0) > policy["target_cpu_percent"] * 1.5:
            recommendations.append({
                "type": "high_cpu",
                "severity": "high",
                "current_value": avg_metrics.get("cpu_percent", 0),
                "threshold": policy["target_cpu_percent"],
                "recommendation": f"Consider scaling up from {current_replicas} to {current_replicas + 1} replicas",
                "reason": "CPU usage significantly above target"
            })

        # Check memory
        if avg_metrics.get("memory_percent", 0) > policy["target_memory_percent"] * 1.5:
            recommendations.append({
                "type": "high_memory",
                "severity": "high",
                "current_value": avg_metrics.get("memory_percent", 0),
                "threshold": policy["target_memory_percent"],
                "recommendation": f"Consider scaling up from {current_replicas} to {current_replicas + 1} replicas",
                "reason": "Memory usage significantly above target"
            })

        # Check QPS
        if avg_metrics.get("requests_per_second", 0) > policy["target_qps"] * 1.5:
            recommendations.append({
                "type": "high_qps",
                "severity": "medium",
                "current_value": avg_metrics.get("requests_per_second", 0),
                "threshold": policy["target_qps"],
                "recommendation": f"Consider scaling up from {current_replicas} to {current_replicas + 1} replicas",
                "reason": "Request rate significantly above target"
            })

        # Check for underutilization
        if current_replicas > policy["min_replicas"]:
            if (avg_metrics.get("cpu_percent", 0) < policy["target_cpu_percent"] * 0.3 and
                avg_metrics.get("memory_percent", 0) < policy["target_memory_percent"] * 0.3 and
                avg_metrics.get("requests_per_second", 0) < policy["target_qps"] * 0.3):
                recommendations.append({
                    "type": "underutilized",
                    "severity": "low",
                    "recommendation": f"Consider scaling down from {current_replicas} to {current_replicas - 1} replicas",
                    "reason": "Resources significantly underutilized"
                })

        return recommendations
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get recommendations: {str(e)}")