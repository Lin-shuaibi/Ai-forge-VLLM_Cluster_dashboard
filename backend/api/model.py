"""Model API routes with remote deployment support."""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from services.vllm_service import vllm_service
from services.remote_deploy_service import remote_deploy_service
from services.log_manager import log_manager

router = APIRouter(prefix="/api/models", tags=["models"])


class StartModelRequest(BaseModel):
    model_path: str
    model_name: str
    cluster_id: Optional[str] = None
    tensor_parallel_size: int = 1
    max_model_len: Optional[int] = None
    gpu_memory_utilization: float = 0.90
    dtype: str = "auto"
    trust_remote_code: bool = True
    enforce_eager: bool = False
    max_num_seqs: int = 256
    port: int = 8000
    extra_args: Optional[List[str]] = None


class RemoteDeployRequest(BaseModel):
    host: str
    username: str
    password: str
    model_path: str
    model_name: str
    tensor_parallel_size: int = 1
    max_model_len: Optional[int] = None
    gpu_memory_utilization: float = 0.90
    dtype: str = "auto"
    trust_remote_code: bool = True
    enforce_eager: bool = False
    max_num_seqs: int = 256
    port: int = 8000
    extra_args: Optional[List[str]] = None


class ModelResponse(BaseModel):
    id: str
    name: str
    path: str
    cluster_id: Optional[str] = None
    port: int
    status: str


class RemoteDeploymentResponse(BaseModel):
    id: str
    host: str
    model_name: str
    model_path: str
    port: int
    status: str
    start_time: Optional[float] = None


# --- Remote deployment routes (BEFORE dynamic model_id routes to avoid conflict) ---

@router.post("/remote-deploy", response_model=dict)
async def remote_deploy(body: RemoteDeployRequest):
    """Deploy model on remote machine via SSH."""
    try:
        deployment_id, tracker = await remote_deploy_service.deploy_model(
            host=body.host,
            username=body.username,
            password=body.password,
            model_path=body.model_path,
            model_name=body.model_name,
            tensor_parallel_size=body.tensor_parallel_size,
            max_model_len=body.max_model_len,
            gpu_memory_utilization=body.gpu_memory_utilization,
            dtype=body.dtype,
            trust_remote_code=body.trust_remote_code,
            enforce_eager=body.enforce_eager,
            max_num_seqs=body.max_num_seqs,
            port=body.port,
            extra_args=body.extra_args,
        )
        return {
            "deployment_id": deployment_id, 
            "status": "deploying", 
            "progress": tracker.get_progress()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/remote", response_model=List[RemoteDeploymentResponse])
async def list_remote_deployments():
    """List all remote deployments."""
    deployments = await remote_deploy_service.list_deployments()
    return [RemoteDeploymentResponse(**d) for d in deployments]


@router.get("/remote/{deployment_id}/status")
async def get_remote_deployment_status(deployment_id: str):
    """Get status of a remote deployment."""
    try:
        status = await remote_deploy_service.get_deployment_status(deployment_id)
        return status
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/remote/{deployment_id}/stop")
async def stop_remote_deployment(deployment_id: str):
    """Stop a remote deployment."""
    try:
        await remote_deploy_service.stop_deployment(deployment_id)
        return {"status": "stopped"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.websocket("/remote/{deployment_id}/logs")
async def remote_deployment_logs(websocket: WebSocket, deployment_id: str):
    """WebSocket for remote deployment logs."""
    await websocket.accept()
    channel = f"remote:{deployment_id}"
    queue = log_manager.subscribe(channel)
    try:
        while True:
            entry = await queue.get()
            await websocket.send_json(entry)
    except WebSocketDisconnect:
        log_manager.unsubscribe(channel, queue)
    except Exception:
        log_manager.unsubscribe(channel, queue)


# --- Local model routes ---

@router.post("/start", response_model=dict)
async def start_model(body: StartModelRequest):
    try:
        model_id, tracker = await vllm_service.start_model_with_progress(
            model_path=body.model_path,
            model_name=body.model_name,
            cluster_id=body.cluster_id,
            tensor_parallel_size=body.tensor_parallel_size,
            max_model_len=body.max_model_len,
            gpu_memory_utilization=body.gpu_memory_utilization,
            dtype=body.dtype,
            trust_remote_code=body.trust_remote_code,
            enforce_eager=body.enforce_eager,
            max_num_seqs=body.max_num_seqs,
            port=body.port,
            extra_args=body.extra_args,
        )
        return {"model_id": model_id, "status": "running", "progress": tracker.get_progress()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{model_id}/progress")
async def get_model_progress(model_id: str):
    """Get progress of model startup."""
    model = vllm_service.models.get(model_id)
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")
    return {"status": model["status"]}


@router.post("/{model_id}/stop")
async def stop_model(model_id: str):
    try:
        await vllm_service.stop_model(model_id)
        return {"status": "stopped"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("", response_model=List[ModelResponse])
async def list_models():
    models = await vllm_service.list_models()
    return [ModelResponse(**m) for m in models]


@router.websocket("/{model_id}/logs")
async def model_logs(websocket: WebSocket, model_id: str):
    await websocket.accept()
    channel = f"model:{model_id}"
    queue = log_manager.subscribe(channel)
    try:
        while True:
            entry = await queue.get()
            await websocket.send_json(entry)
    except WebSocketDisconnect:
        log_manager.unsubscribe(channel, queue)
    except Exception:
        log_manager.unsubscribe(channel, queue)