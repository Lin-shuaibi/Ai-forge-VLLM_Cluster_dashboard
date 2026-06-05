"""Marketplace API routes."""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel

from ..services.marketplace_service import marketplace_service
from ..services.auth_service import get_current_user

router = APIRouter(prefix="/marketplace", tags=["marketplace"])


class ModelTemplate(BaseModel):
    id: str
    name: str
    model_name: str
    description: Optional[str] = None
    category: str
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


@router.get("/templates", response_model=List[ModelTemplate])
async def get_templates(
    source: str = Query("all", description="数据源: all, modelscope, local"),
    category: str = Query(None, description="模型类别"),
    search: str = Query(None, description="搜索关键词"),
    page: int = Query(1, ge=1, description="页码"),
    per_page: int = Query(20, ge=1, le=100, description="每页数量")
):
    """获取模型模板列表"""
    try:
        templates = await marketplace_service.get_templates(
            source=source,
            category=category,
            search=search,
            page=page,
            per_page=per_page
        )
        return templates
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取模板失败: {str(e)}")


@router.get("/popular", response_model=List[ModelTemplate])
async def get_popular_models(
    limit: int = Query(20, ge=1, le=100, description="数量限制"),
    source: str = Query("all", description="数据源: all, modelscope, local")
):
    """获取热门模型"""
    try:
        models = await marketplace_service.get_popular_models(
            limit=limit,
            source=source
        )
        return models
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取热门模型失败: {str(e)}")


@router.get("/templates/{model_id}", response_model=ModelDetails)
async def get_model_details(model_id: str):
    """获取模型详情"""
    try:
        details = await marketplace_service.get_model_details(model_id)
        if not details:
            raise HTTPException(status_code=404, detail="模型不存在")
        
        # Get model files
        files = await marketplace_service.get_model_files(model_id)
        details["files"] = files
        
        return details
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取模型详情失败: {str(e)}")


@router.get("/templates/{model_id}/files")
async def get_model_files(model_id: str):
    """获取模型文件列表"""
    try:
        files = await marketplace_service.get_model_files(model_id)
        return {"files": files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取文件列表失败: {str(e)}")


@router.post("/templates")
async def add_local_template(template: ModelTemplate):
    """添加本地模板"""
    try:
        success = marketplace_service.add_local_template(template.dict())
        if not success:
            raise HTTPException(status_code=500, detail="添加模板失败")
        return {"message": "模板添加成功", "id": template.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"添加模板失败: {str(e)}")


@router.get("/favorites")
async def get_user_favorites(
    current_user: dict = Depends(get_current_user)
):
    """获取用户收藏"""
    try:
        favorites = marketplace_service.get_user_favorites(current_user["id"])
        return {"favorites": favorites}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取收藏失败: {str(e)}")


@router.post("/favorites/{model_id}")
async def add_favorite(
    model_id: str,
    current_user: dict = Depends(get_current_user)
):
    """添加收藏"""
    try:
        success = marketplace_service.add_favorite(current_user["id"], model_id)
        if not success:
            raise HTTPException(status_code=500, detail="添加收藏失败")
        return {"message": "收藏成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"添加收藏失败: {str(e)}")


@router.delete("/favorites/{model_id}")
async def remove_favorite(
    model_id: str,
    current_user: dict = Depends(get_current_user)
):
    """移除收藏"""
    try:
        success = marketplace_service.remove_favorite(current_user["id"], model_id)
        if not success:
            raise HTTPException(status_code=500, detail="移除收藏失败")
        return {"message": "移除收藏成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"移除收藏失败: {str(e)}")


@router.get("/categories")
async def get_categories():
    """获取可用分类"""
    try:
        categories = marketplace_service.get_categories()
        return {"categories": categories}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取分类失败: {str(e)}")


@router.get("/sources")
async def get_sources():
    """获取可用数据源"""
    try:
        sources = marketplace_service.get_sources()
        return {"sources": sources}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取数据源失败: {str(e)}")

