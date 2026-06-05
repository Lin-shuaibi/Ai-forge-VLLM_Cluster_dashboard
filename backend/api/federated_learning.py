"""Federated Learning API."""
import json
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel, Field

from services.fl_service import fl_service
from services.auth_service import get_current_user, require_permission, TokenData

router = APIRouter(prefix="/federated-learning", tags=["federated-learning"])


class ProjectCreate(BaseModel):
    name: str = Field(..., description="Project name")
    base_model: str = Field(..., description="Base model name")
    description: str = Field("", description="Project description")
    aggregation_strategy: str = Field("fedavg", description="Aggregation strategy")
    num_clients: int = Field(2, ge=2, le=100, description="Expected number of clients")
    min_clients: int = Field(2, ge=2, le=100, description="Minimum clients per round")
    local_epochs: int = Field(5, ge=1, le=100, description="Local epochs per round")
    batch_size: int = Field(32, ge=1, le=1024, description="Batch size")
    learning_rate: float = Field(0.01, ge=0.0001, le=1.0, description="Learning rate")
    privacy_budget: float = Field(10.0, ge=0.1, le=100, description="Privacy budget epsilon")
    differential_privacy: bool = Field(False, description="Enable differential privacy")
    secure_aggregation: bool = Field(False, description="Enable secure aggregation")


class ClientRegister(BaseModel):
    client_id: str = Field(..., description="Client identifier")
    client_name: str = Field(None, description="Human-readable client name")
    endpoint_url: str = Field(None, description="Client endpoint URL")
    data_size: int = Field(0, ge=0, description="Number of data samples")


class ClientResult(BaseModel):
    client_id: str = Field(..., description="Client identifier")
    local_accuracy: float = Field(..., ge=0, le=1, description="Local accuracy")
    local_loss: float = Field(..., ge=0, description="Local loss")
    training_time_ms: float = Field(0, ge=0, description="Training time in milliseconds")
    data_used: int = Field(0, ge=0, description="Number of data samples used")
    model_delta_size: int = Field(0, ge=0, description="Model delta size in bytes")


class AggregateRequest(BaseModel):
    global_accuracy: float = Field(0, ge=0, le=1, description="Global model accuracy")
    global_loss: float = Field(0, ge=0, description="Global model loss")
    aggregation_time_ms: float = Field(0, ge=0, description="Aggregation time in milliseconds")


class ClientStatusUpdate(BaseModel):
    status: str = Field(..., description="New client status")


class SimulateRequest(BaseModel):
    num_rounds: int = Field(10, ge=1, le=100, description="Number of rounds to simulate")


@router.post("/projects", response_model=dict)
async def create_project(
    project: ProjectCreate,
    current_user: TokenData = Depends(require_permission("federated_learning", "create"))
):
    try:
        result = fl_service.create_project(
            name=project.name,
            base_model=project.base_model,
            description=project.description,
            aggregation_strategy=project.aggregation_strategy,
            num_clients=project.num_clients,
            min_clients=project.min_clients,
            local_epochs=project.local_epochs,
            batch_size=project.batch_size,
            learning_rate=project.learning_rate,
            privacy_budget=project.privacy_budget,
            differential_privacy=project.differential_privacy,
            secure_aggregation=project.secure_aggregation
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects", response_model=List[dict])
async def list_projects(
    status: Optional[str] = Query(None, description="Filter by status"),
    current_user: TokenData = Depends(require_permission("federated_learning", "read"))
):
    try:
        return fl_service.list_projects(status)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}", response_model=dict)
async def get_project(
    project_id: int,
    current_user: TokenData = Depends(require_permission("federated_learning", "read"))
):
    try:
        project = fl_service.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
        return project
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/projects/{project_id}", response_model=dict)
async def delete_project(
    project_id: int,
    current_user: TokenData = Depends(require_permission("federated_learning", "delete"))
):
    try:
        fl_service.delete_project(project_id)
        return {"message": f"Project {project_id} deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/clients", response_model=dict)
async def register_client(
    project_id: int,
    client: ClientRegister,
    current_user: TokenData = Depends(require_permission("federated_learning", "create"))
):
    try:
        return fl_service.register_client(
            project_id=project_id,
            client_id=client.client_id,
            client_name=client.client_name,
            endpoint_url=client.endpoint_url,
            data_size=client.data_size
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/clients", response_model=List[dict])
async def get_clients(
    project_id: int,
    current_user: TokenData = Depends(require_permission("federated_learning", "read"))
):
    try:
        return fl_service.get_clients(project_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/projects/{project_id}/clients/{client_id}/status", response_model=dict)
async def update_client_status(
    project_id: int,
    client_id: str,
    status_update: ClientStatusUpdate,
    current_user: TokenData = Depends(require_permission("federated_learning", "update"))
):
    try:
        return fl_service.update_client_status(project_id, client_id, status_update.status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/rounds/start", response_model=dict)
async def start_training_round(
    project_id: int,
    current_user: TokenData = Depends(require_permission("federated_learning", "update"))
):
    try:
        return fl_service.start_training_round(project_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rounds/{round_id}/client-results", response_model=dict)
async def submit_client_result(
    round_id: int,
    result: ClientResult,
    current_user: TokenData = Depends(require_permission("federated_learning", "create"))
):
    try:
        return fl_service.submit_client_result(
            round_id=round_id,
            client_id=result.client_id,
            local_accuracy=result.local_accuracy,
            local_loss=result.local_loss,
            training_time_ms=result.training_time_ms,
            data_used=result.data_used,
            model_delta_size=result.model_delta_size
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rounds/{round_id}/aggregate", response_model=dict)
async def aggregate_round(
    round_id: int,
    aggregate: AggregateRequest,
    current_user: TokenData = Depends(require_permission("federated_learning", "update"))
):
    try:
        return fl_service.aggregate_round(
            round_id=round_id,
            global_accuracy=aggregate.global_accuracy,
            global_loss=aggregate.global_loss,
            aggregation_time_ms=aggregate.aggregation_time_ms
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/progress", response_model=dict)
async def get_training_progress(
    project_id: int,
    current_user: TokenData = Depends(require_permission("federated_learning", "read"))
):
    try:
        return fl_service.get_training_progress(project_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/simulate", response_model=dict)
async def simulate_training(
    project_id: int,
    request: SimulateRequest,
    current_user: TokenData = Depends(require_permission("federated_learning", "create"))
):
    try:
        return fl_service.simulate_training(project_id, request.num_rounds)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategies", response_model=dict)
async def get_strategies(
    current_user: TokenData = Depends(require_permission("federated_learning", "read"))
):
    try:
        return fl_service.get_aggregation_strategy_info()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))