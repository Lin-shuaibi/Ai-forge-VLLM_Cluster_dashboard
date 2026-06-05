"""Dashboard API placeholder."""
from fastapi import APIRouter

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

@router.get("/")
async def get_dashboard():
    return {"message": "Dashboard API placeholder"}