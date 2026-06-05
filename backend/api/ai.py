"""AI Chat API routes."""
from typing import Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from services.ai_chat_service import ai_chat_service

router = APIRouter(prefix="/api/ai", tags=["ai"])


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


class AIConfigUpdate(BaseModel):
    api_url: Optional[str] = None
    api_key: Optional[str] = None
    model_name: Optional[str] = None
    use_local_vllm: Optional[bool] = None
    local_vllm_url: Optional[str] = None
    local_model_name: Optional[str] = None


@router.get("/config")
async def get_ai_config():
    return ai_chat_service.get_config()


@router.put("/config")
async def update_ai_config(body: AIConfigUpdate):
    ai_chat_service.update_config(**body.model_dump(exclude_none=True))
    return ai_chat_service.get_config()


@router.post("/chat")
async def chat(body: ChatRequest):
    """Stream AI chat response with function calling."""
    from services.docker_service import docker_service
    from services.vllm_service import vllm_service

    # Gather platform context
    try:
        clusters = await docker_service.list_clusters()
        models = await vllm_service.list_models()
        context = {
            "clusters": clusters,
            "models": models,
        }
    except Exception:
        context = {}

    async def event_stream():
        async for chunk in ai_chat_service.chat(
            session_id=body.session_id,
            message=body.message,
            context_data=context,
        ):
            yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/clear")
async def clear_session(session_id: str = "default"):
    ai_chat_service.clear_session(session_id)
    return {"status": "cleared"}