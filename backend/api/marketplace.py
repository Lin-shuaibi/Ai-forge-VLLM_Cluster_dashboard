"""Marketplace API with ModelScope integration."""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel

from services.marketplace_service import marketplace_service
from services.download_service import model_download_service

router = APIRouter()


class ModelTemplate(BaseModel):
    id: str
    name: str
    model_name: str
    description: Optional[str] = None
    category: str = "llm"
    tags: List[str] = []
    downloads: int = 0
    likes: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    author: Optional[str] = None
    framework: Optional[str] = None
    task: Optional[str] = None
    is_public: bool = True
    model_card: Optional[str] = None
    recommended_config: dict = {}
    source: str = "local"


class ModelDetails(ModelTemplate):
    files: List[dict] = []
    config: dict = {}


@router.get("/templates")
async def get_templates(
    source: str = Query("all", description="all | modelscope | local"),
    category: str = Query(None),
    search: str = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100)
):
    """Get model templates from ModelScope or local."""
    try:
        templates = await marketplace_service.get_templates(
            source=source, category=category, search=search,
            page=page, per_page=per_page
        )
        return {"templates": templates, "source": source, "total": len(templates)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch templates: {str(e)}")


@router.get("/popular")
async def get_popular(
    limit: int = Query(20, ge=1, le=100),
    source: str = Query("all")
):
    """Get popular models."""
    try:
        models = await marketplace_service.get_popular_models(limit=limit, source=source)
        return {"models": models, "source": source}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch popular models: {str(e)}")


@router.get("/templates/{model_id}")
async def get_model_detail(model_id: str):
    """Get model details with files."""
    try:
        details = await marketplace_service.get_model_details(model_id)
        if not details:
            raise HTTPException(status_code=404, detail="Model not found")
        files = await marketplace_service.get_model_files(model_id)
        details["files"] = files
        return details
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch model details: {str(e)}")


@router.get("/templates/{model_id}/files")
async def get_model_files(model_id: str):
    """Get model file list."""
    try:
        files = await marketplace_service.get_model_files(model_id)
        return {"model_id": model_id, "files": files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch files: {str(e)}")


@router.post("/templates")
async def add_template(template: ModelTemplate):
    """Add local template."""
    try:
        success = marketplace_service.add_local_template(template.dict())
        if not success:
            raise HTTPException(status_code=500, detail="Failed to add template")
        return {"message": "Template added", "id": template.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add template: {str(e)}")


@router.get("/categories")
async def get_categories():
    """Get available model categories."""
    try:
        return {"categories": marketplace_service.get_categories()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch categories: {str(e)}")


@router.get("/sources")
async def get_sources():
    """Get available data sources."""
    try:
        return {"sources": marketplace_service.get_sources()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch sources: {str(e)}")


@router.post("/favorites/{model_id}")
async def add_favorite(model_id: str):
    """Add model to favorites."""
    try:
        success = marketplace_service.add_favorite("default", model_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to add favorite")
        return {"message": "Added to favorites"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed: {str(e)}")


@router.delete("/favorites/{model_id}")
async def remove_favorite(model_id: str):
    """Remove model from favorites."""
    try:
        success = marketplace_service.remove_favorite("default", model_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to remove favorite")
        return {"message": "Removed from favorites"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed: {str(e)}")


@router.get("/favorites")
async def get_favorites():
    """Get user favorites."""
    try:
        favs = marketplace_service.get_user_favorites("default")
        return {"favorites": favs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed: {str(e)}")


@router.post("/templates/{template_id}/use")
async def use_template(template_id: str):
    """Use a template, create download task, and return config."""
    try:
        details = await marketplace_service.get_model_details(template_id)
        if not details:
            raise HTTPException(status_code=404, detail="Model not found")
        
        # Create download task
        model_name = details.get("model_name", details.get("name", ""))
        task_id = None
        if model_name:
            task_id = await model_download_service.create_download_task(
                model_name=model_name,
                local_path=""
            )
        
        return {
            "success": True,
            "model": {
                "id": details["id"],
                "name": details["name"],
                "model_name": details["model_name"]
            },
            "config": details.get("recommended_config", {}),
            "model_card": details.get("model_card", ""),
            "download_task_id": task_id
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed: {str(e)}")
