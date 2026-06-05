"""Model version management API."""
import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel, Field

from services.model_version_service import (
    model_version_service, ModelVersion, ModelVersionService
)
from services.auth_service import get_current_user, require_permission, TokenData
from services.error_handlers import NotFoundError, ConflictError

router = APIRouter(prefix="/model-versions", tags=["model-versions"])


class ModelVersionCreate(BaseModel):
    model_name: str = Field(..., description="Name of the model")
    version: str = Field(..., description="Version identifier")
    path: str = Field(..., description="Path to model files")
    size_mb: float = Field(..., description="Size in MB")
    framework: str = Field("vllm", description="Model framework")
    description: str = Field("", description="Version description")
    config: dict = Field({}, description="Model configuration")
    tags: List[str] = Field([], description="Tags for categorization")
    parent_version: Optional[str] = Field(None, description="Parent version for rollback")
    created_by: str = Field("system", description="Creator identifier")


class ModelVersionUpdate(BaseModel):
    description: Optional[str] = None
    config: Optional[dict] = None
    tags: Optional[List[str]] = None
    is_active: Optional[bool] = None


class DeploymentCreate(BaseModel):
    host: Optional[str] = None
    port: Optional[int] = None
    gpu_count: int = Field(1, ge=1, le=8)


class DeploymentStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(pending|running|stopped|failed)$")


@router.post("", response_model=dict)
async def create_model_version(
    version_data: ModelVersionCreate,
    current_user: TokenData = Depends(require_permission("model_version", "create"))
):
    """Register a new model version."""
    try:
        mv = ModelVersion(
            model_name=version_data.model_name,
            version=version_data.version,
            path=version_data.path,
            size_mb=version_data.size_mb,
            framework=version_data.framework,
            description=version_data.description,
            config=version_data.config,
            tags=version_data.tags,
            parent_version=version_data.parent_version,
            created_by=current_user.username
        )
        result = model_version_service.register_version(mv)
        return result
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create version: {str(e)}")


@router.get("", response_model=List[dict])
async def list_model_versions(
    model_name: Optional[str] = Query(None, description="Filter by model name"),
    active_only: bool = Query(False, description="Only show active versions"),
    current_user: TokenData = Depends(require_permission("model_version", "read"))
):
    """List model versions."""
    try:
        versions = model_version_service.list_versions(model_name, active_only)
        return versions
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list versions: {str(e)}")


@router.get("/{version_id}", response_model=dict)
async def get_model_version(
    version_id: int,
    current_user: TokenData = Depends(require_permission("model_version", "read"))
):
    """Get a specific model version."""
    try:
        version = model_version_service.get_version(version_id)
        return version
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get version: {str(e)}")


@router.get("/model/{model_name}/latest", response_model=dict)
async def get_latest_version(
    model_name: str,
    current_user: TokenData = Depends(require_permission("model_version", "read"))
):
    """Get the latest active version of a model."""
    try:
        version = model_version_service.get_latest_version(model_name)
        if not version:
            raise HTTPException(status_code=404, detail=f"No active version found for {model_name}")
        return version
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get latest version: {str(e)}")


@router.put("/{version_id}/activate", response_model=dict)
async def activate_model_version(
    version_id: int,
    current_user: TokenData = Depends(require_permission("model_version", "update"))
):
    """Activate a model version."""
    try:
        version = model_version_service.activate_version(version_id)
        return version
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to activate version: {str(e)}")


@router.delete("/{version_id}", response_model=dict)
async def delete_model_version(
    version_id: int,
    current_user: TokenData = Depends(require_permission("model_version", "delete"))
):
    """Delete a model version."""
    try:
        success = model_version_service.delete_version(version_id)
        return {"deleted": success, "version_id": version_id}
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete version: {str(e)}")


@router.get("/{model_name}/compare", response_model=dict)
async def compare_versions(
    model_name: str,
    v1: str = Query(..., description="First version"),
    v2: str = Query(..., description="Second version"),
    current_user: TokenData = Depends(require_permission("model_version", "read"))
):
    """Compare two model versions."""
    try:
        result = model_version_service.compare_versions(model_name, v1, v2)
        return result
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to compare versions: {str(e)}")


@router.post("/{model_name}/rollback", response_model=dict)
async def rollback_model(
    model_name: str,
    target_version_id: int = Body(..., embed=True),
    current_user: TokenData = Depends(require_permission("model_version", "update"))
):
    """Rollback to a previous version."""
    try:
        result = model_version_service.rollback(model_name, target_version_id)
        return result
    except (NotFoundError, ConflictError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to rollback: {str(e)}")


@router.post("/{version_id}/deploy", response_model=dict)
async def create_deployment(
    version_id: int,
    deployment_data: DeploymentCreate,
    current_user: TokenData = Depends(require_permission("model_version", "execute"))
):
    """Create a deployment for a model version."""
    try:
        result = model_version_service.create_deployment(
            version_id,
            deployment_data.host,
            deployment_data.port,
            deployment_data.gpu_count
        )
        return result
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create deployment: {str(e)}")


@router.put("/deployments/{deployment_id}", response_model=dict)
async def update_deployment_status(
    deployment_id: int,
    status_update: DeploymentStatusUpdate,
    current_user: TokenData = Depends(require_permission("model_version", "update"))
):
    """Update deployment status."""
    try:
        result = model_version_service.update_deployment_status(
            deployment_id, status_update.status)
        return result
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update deployment: {str(e)}")


@router.get("/{version_id}/deployments", response_model=List[dict])
async def get_deployment_history(
    version_id: int,
    current_user: TokenData = Depends(require_permission("model_version", "read"))
):
    """Get deployment history for a version."""
    try:
        history = model_version_service.get_deployment_history(version_id)
        return history
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get deployment history: {str(e)}")


@router.get("/stats/summary", response_model=dict)
async def get_version_stats(
    current_user: TokenData = Depends(require_permission("model_version", "read"))
):
    """Get version statistics."""
    try:
        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            c.execute("SELECT COUNT(*) as total_versions FROM model_versions")
            total = c.fetchone()["total_versions"]

            c.execute("SELECT COUNT(*) as active_versions FROM model_versions WHERE is_active = 1")
            active = c.fetchone()["active_versions"]

            c.execute("SELECT COUNT(DISTINCT model_name) as unique_models FROM model_versions")
            models = c.fetchone()["unique_models"]

            c.execute("SELECT SUM(size_mb) as total_size_mb FROM model_versions")
            total_size = c.fetchone()["total_size_mb"] or 0

            c.execute("SELECT SUM(download_count) as total_downloads FROM model_versions")
            downloads = c.fetchone()["total_downloads"] or 0

            return {
                "total_versions": total,
                "active_versions": active,
                "unique_models": models,
                "total_size_mb": round(total_size, 2),
                "total_downloads": downloads
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")