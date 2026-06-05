"""VLLM Cluster Dashboard - Main Application."""
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from config import settings
from api.settings import router as settings_router
from api.cluster import router as cluster_router
from api.model import router as model_router
from api.benchmark import router as benchmark_router
from api.logs import router as logs_router
from api.ai import router as ai_router
from api.download import router as download_router
from api.gpu import router as gpu_router
from api.features import router as features_router
from api.marketplace import router as marketplace_router

app = FastAPI(
    title=settings.app_title,
    version=settings.app_version,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(settings_router)
app.include_router(cluster_router)
app.include_router(model_router)
app.include_router(benchmark_router)
app.include_router(logs_router)
app.include_router(ai_router)
app.include_router(download_router)
app.include_router(gpu_router)
app.include_router(features_router, prefix="/api/features", tags=["features"])
app.include_router(marketplace_router, prefix="/api/marketplace", tags=["marketplace"])

@app.get("/api/status")
async def status():
    from services.docker_service import docker_service
    from services.vllm_service import vllm_service
    docker_ok = await docker_service.health_check()
    clusters = await docker_service.list_clusters()
    models = await vllm_service.list_models()
    benchmarks = await vllm_service.list_benchmarks()
    return {
        "docker": docker_ok,
        "clusters": len(clusters),
        "models": len(models),
        "benchmarks": len(benchmarks),
        "clusters_list": clusters,
        "models_list": models,
    }

frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        log_level="info",
    )
