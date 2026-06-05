"""Cluster API routes."""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from services.docker_service import docker_service
from services.log_manager import log_manager

router = APIRouter(prefix="/api/clusters", tags=["clusters"])


class NodeSpec(BaseModel):
    ip: str
    username: str = "root"
    password: str = ""
    gpus: int = 1


class CreateClusterRequest(BaseModel):
    name: str
    nodes: List[NodeSpec]
    image: Optional[str] = None
    use_combined_image: bool = False


class ClusterResponse(BaseModel):
    id: str
    name: str
    image: str
    use_combined: bool
    node_count: int
    head_ip: Optional[str] = None
    status: str


class ClusterDetailResponse(BaseModel):
    id: str
    name: str
    image: str
    use_combined: bool
    nodes: list
    containers: list
    head_ip: Optional[str] = None
    network: str
    status: str


@router.post("", response_model=dict)
async def create_cluster(body: CreateClusterRequest):
    from config import settings
    image = body.image
    if not image:
        if body.use_combined_image and settings.ray_vllm_image:
            image = settings.ray_vllm_image
        elif settings.ray_vllm_image:
            image = settings.ray_vllm_image
        else:
            image = settings.ray_image

    nodes = [n.model_dump() for n in body.nodes]
    try:
        cluster_id, tracker = await docker_service.create_cluster_with_progress(
            name=body.name,
            nodes=nodes,
            image=image,
            use_combined=body.use_combined_image,
        )
        return {
            "cluster_id": cluster_id, 
            "status": "running",
            "progress": tracker.get_progress()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{cluster_id}/progress")
async def get_cluster_progress(cluster_id: str):
    """Get progress of cluster creation."""
    cluster = await docker_service.get_cluster(cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="集群不存在")
    
    tracker = cluster.get("progress_tracker")
    if tracker:
        return tracker.get_progress()
    else:
        return {"status": "no_progress_data"}


@router.get("", response_model=List[ClusterResponse])
async def list_clusters():
    clusters = await docker_service.list_clusters()
    return [ClusterResponse(**c) for c in clusters]


@router.get("/{cluster_id}", response_model=ClusterDetailResponse)
async def get_cluster(cluster_id: str):
    cluster = await docker_service.get_cluster(cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="集群不存在")
    return ClusterDetailResponse(**cluster)


@router.delete("/{cluster_id}")
async def delete_cluster(cluster_id: str):
    try:
        await docker_service.delete_cluster(cluster_id)
        return {"status": "deleted"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.websocket("/{cluster_id}/logs")
async def cluster_logs(websocket: WebSocket, cluster_id: str):
    await websocket.accept()
    channel = f"cluster:{cluster_id}"
    queue = log_manager.subscribe(channel)
    try:
        while True:
            entry = await queue.get()
            await websocket.send_json(entry)
    except WebSocketDisconnect:
        log_manager.unsubscribe(channel, queue)
    except Exception:
        log_manager.unsubscribe(channel, queue)