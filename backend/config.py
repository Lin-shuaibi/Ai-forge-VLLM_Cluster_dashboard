"""Application configuration."""
import os
import json
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings

SETTINGS_FILE = Path(__file__).parent / "data" / "settings.json"


class Settings(BaseSettings):
    app_title: str = "VLLM Cluster Dashboard"
    app_version: str = "1.0.0"
    host: str = "0.0.0.0"
    port: int = 8000

    # Docker image settings
    ray_image: str = "rayproject/ray:latest"
    vllm_image: str = "vllm/vllm-openai:latest"
    ray_vllm_image: str = ""
    use_combined_image: bool = False
    registry_auth: Optional[str] = None

    image_cache_dir: str = "/tmp/vllm-image-cache"
    ray_head_port: int = 6379
    ray_dashboard_port: int = 8265
    default_model_path: str = "/models"
    default_tensor_parallel: int = 1
    default_gpu_memory_utilization: float = 0.90
    cluster_network_name: str = "vllm-cluster-net"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


def load_settings() -> Settings:
    """Create Settings, then override from persisted JSON file."""
    s = Settings()
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            for key in ("ray_image", "vllm_image", "ray_vllm_image", "use_combined_image", "registry_auth"):
                if key in data:
                    setattr(s, key, data[key])
        except Exception:
            pass
    return s


def save_settings(s: Settings):
    """Persist image settings to JSON file."""
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "ray_image": s.ray_image,
        "vllm_image": s.vllm_image,
        "ray_vllm_image": s.ray_vllm_image,
        "use_combined_image": s.use_combined_image,
        "registry_auth": s.registry_auth,
    }
    SETTINGS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


settings = load_settings()
