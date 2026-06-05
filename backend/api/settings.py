"""Settings API routes."""
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import docker
from config import settings, save_settings

router = APIRouter(prefix="/api/settings", tags=["settings"])


class ImageSettings(BaseModel):
    ray_image: str = ""
    vllm_image: str = ""
    ray_vllm_image: str = ""
    use_combined_image: bool = False
    registry_auth: Optional[str] = None  # Base64 encoded docker config auth


class ImageCheckRequest(BaseModel):
    image_name: str
    registry_auth: Optional[str] = None


class ImageCheckResponse(BaseModel):
    exists: bool
    pulled: bool = False
    error: Optional[str] = None
    size_mb: Optional[float] = None
    layers: Optional[int] = None


class RegistryAuth(BaseModel):
    username: str
    password: str
    registry: str = ""


class SettingsResponse(BaseModel):
    ray_image: str
    vllm_image: str
    ray_vllm_image: str
    use_combined_image: bool
    registry_auth: Optional[str] = None


@router.get("", response_model=SettingsResponse)
async def get_settings():
    return SettingsResponse(
        ray_image=settings.ray_image,
        vllm_image=settings.vllm_image,
        ray_vllm_image=settings.ray_vllm_image,
        use_combined_image=settings.use_combined_image,
        registry_auth=getattr(settings, 'registry_auth', None),
    )


@router.put("/images", response_model=SettingsResponse)
async def update_image_settings(body: ImageSettings):
    if body.ray_image:
        settings.ray_image = body.ray_image
    if body.vllm_image:
        settings.vllm_image = body.vllm_image
    if body.ray_vllm_image:
        settings.ray_vllm_image = body.ray_vllm_image
    settings.use_combined_image = body.use_combined_image
    if body.registry_auth is not None:
        settings.registry_auth = body.registry_auth
    save_settings(settings)
    return SettingsResponse(
        ray_image=settings.ray_image,
        vllm_image=settings.vllm_image,
        ray_vllm_image=settings.ray_vllm_image,
        use_combined_image=settings.use_combined_image,
        registry_auth=getattr(settings, 'registry_auth', None),
    )


@router.post("/check-image", response_model=ImageCheckResponse)
async def check_image(request: ImageCheckRequest):
    """检查镜像是否存在，不存在则拉取"""
    try:
        client = docker.from_env()
        
        # 检查镜像是否存在
        try:
            image = client.images.get(request.image_name)
            size_mb = sum((layer.get("Size", 0) if isinstance(layer, dict) else layer.size) for layer in image.history()) / (1024 * 1024)
            return ImageCheckResponse(
                exists=True,
                size_mb=round(size_mb, 2),
                layers=len(image.history())
            )
        except docker.errors.ImageNotFound:
            # 镜像不存在，尝试拉取
            try:
                auth_config = None
                if request.registry_auth:
                    import base64
                    import json
                    auth_data = json.loads(base64.b64decode(request.registry_auth).decode())
                    auth_config = {
                        "username": auth_data.get("username"),
                        "password": auth_data.get("password"),
                        "registry": auth_data.get("registry", "")
                    }
                
                # 拉取镜像并显示进度
                from services.log_manager import log_manager
                log_manager.emit("image_pull", "info", f"开始拉取镜像: {request.image_name}")
                
                pull_result = client.images.pull(
                    request.image_name,
                    auth_config=auth_config,
                    stream=True,
                    decode=True
                )
                
                for line in pull_result:
                    if "status" in line:
                        log_manager.emit("image_pull", "info", 
                                       f"{request.image_name}: {line.get('status', '')} {line.get('progress', '')}")
                
                # 获取拉取后的镜像信息
                image = client.images.get(request.image_name)
                size_mb = sum((layer.get("Size", 0) if isinstance(layer, dict) else layer.size) for layer in image.history()) / (1024 * 1024)
                log_manager.emit("image_pull", "success", f"镜像拉取完成: {request.image_name} ({size_mb:.2f} MB)")
                
                return ImageCheckResponse(
                    exists=True,
                    pulled=True,
                    size_mb=round(size_mb, 2),
                    layers=len(image.history())
                )
            except Exception as pull_error:
                error_msg = f"镜像拉取失败: {str(pull_error)}"
                log_manager.emit("image_pull", "error", error_msg)
                return ImageCheckResponse(
                    exists=False,
                    error=error_msg
                )
    except Exception as e:
        return ImageCheckResponse(
            exists=False,
            error=f"Docker连接失败: {str(e)}"
        )


@router.get("/health")
async def health_check():
    from services.docker_service import docker_service
    docker_ok = await docker_service.health_check()
    return {"docker": docker_ok, "status": "ok" if docker_ok else "docker_unavailable"}