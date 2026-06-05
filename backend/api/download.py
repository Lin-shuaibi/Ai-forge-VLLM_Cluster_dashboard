"""Model download API - local and remote download management."""
from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.download_service import model_download_service
from services.remote_download_service import remote_download_service

router = APIRouter(prefix="/api/download")


# ========== Local Download Endpoints (existing) ==========

class DownloadRequest(BaseModel):
    model_name: str
    local_path: Optional[str] = None


@router.get("/local")
async def list_local_tasks():
    """Get all local download tasks."""
    tasks = await model_download_service.list_tasks()
    return tasks


@router.post("/local/start")
async def create_download_task(body: DownloadRequest):
    """Create a new local download task."""
    task_id = await model_download_service.create_download_task(
        model_name=body.model_name,
        local_path=body.local_path
    )
    return {"task_id": task_id, "message": "Download task created"}


@router.get("/local/logs")
async def get_download_logs():
    """Get logs and speeds for all tasks."""
    return {
        "logs": model_download_service.get_logs(),
        "speeds": model_download_service.get_speeds()
    }


@router.post("/local/{task_id}/pause")
async def pause_download_task(task_id: str):
    """Pause a download task."""
    success = await model_download_service.pause_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found or cannot pause")
    return {"message": "Task paused"}


@router.post("/local/{task_id}/stop")
async def stop_download_task(task_id: str):
    """Stop a download task and delete files."""
    success = await model_download_service.stop_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found or cannot stop")
    return {"message": "Task stopped and files deleted"}


@router.post("/local/{task_id}/resume")
async def resume_download_task(task_id: str):
    """Resume a download task."""
    success = await model_download_service.resume_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found or cannot resume")
    return {"message": "Task resumed"}


# ========== Remote Download Endpoints (new) ==========

class RemoteDownloadRequest(BaseModel):
    host: str
    username: str
    password: str
    model_id: str
    target_dir: str
    source: str = "huggingface"  # "huggingface" | "modelscope"
    hf_token: Optional[str] = None


@router.post("/remote")
async def start_remote_download(body: RemoteDownloadRequest):
    """Start a remote model download via SSH."""
    if body.source not in ("huggingface", "modelscope"):
        raise HTTPException(status_code=400, detail="source must be 'huggingface' or 'modelscope'")

    task_id = await remote_download_service.download_model(
        host=body.host,
        username=body.username,
        password=body.password,
        model_id=body.model_id,
        target_dir=body.target_dir,
        source=body.source,
        hf_token=body.hf_token,
    )
    return {"task_id": task_id, "status": "downloading"}


@router.get("/status/{task_id}")
async def get_remote_status(task_id: str):
    """Get remote download task status."""
    status = remote_download_service.get_task_status(task_id)
    return status


@router.get("/list")
async def list_remote_tasks():
    """List all remote download tasks."""
    return remote_download_service.list_tasks()


@router.delete("/{task_id}")
async def cancel_remote_task(task_id: str):
    """Cancel a remote download task."""
    remote_download_service.close_ssh(task_id)
    return {"message": f"Task {task_id} cancelled"}


@router.get("/check-tools")
async def check_tools():
    """Check available download tools on local machine."""
    import subprocess

    def check_cli(name: str) -> bool:
        try:
            result = subprocess.run(
                [name, "--version"], capture_output=True, timeout=10
            )
            return result.returncode == 0
        except Exception:
            return False

    return {
        "huggingface": check_cli("huggingface-cli"),
        "modelscope": check_cli("modelscope"),
    }
