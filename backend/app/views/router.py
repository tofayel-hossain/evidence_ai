import os
from fastapi import APIRouter
from fastapi.responses import FileResponse
from backend.app.config import BASE_DIR, settings

views_router = APIRouter(tags=["Views"])

FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

@views_router.get("/health")
def health_check():
    """Application health and status check."""
    return {
        "status": "healthy",
        "project": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "database": "configured",
        "llm_provider": settings.LLM_PROVIDER
    }

@views_router.get("/")
def serve_index():
    """Serves the main EvidenceAI single-page application."""
    index_file = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "EvidenceAI API is running. Build frontend to view interface."}
