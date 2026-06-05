"""Chat API placeholder."""
from fastapi import APIRouter

router = APIRouter(prefix="/api/chat", tags=["chat"])

@router.get("/")
async def get_chat():
    return {"message": "Chat API placeholder"}