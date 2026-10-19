import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.config import settings, BASE_DIR
from backend.app.database import engine, Base
import backend.app.models  # Register all SQLAlchemy models

# Import Controllers
from backend.app.controllers.auth_controller import router as auth_router
from backend.app.controllers.document_controller import router as document_router
from backend.app.controllers.query_controller import router as query_router
from backend.app.controllers.verification_controller import router as verification_router
from backend.app.controllers.conversation_controller import router as conversation_router
from backend.app.views.router import views_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure database schema is created
    Base.metadata.create_all(bind=engine)
    # Ensure directories exist
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.INDEX_DIR, exist_ok=True)
    yield
    # Shutdown

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="EvidenceAI — AI-Powered Research Assistant with Claim-Level Hallucination Detection & Citation Validation",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Cross-Origin Resource Sharing (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Controllers (MVC Architecture)
api_prefix = settings.API_V1_STR
app.include_router(auth_router, prefix=api_prefix)
app.include_router(document_router, prefix=api_prefix)
app.include_router(query_router, prefix=api_prefix)
app.include_router(verification_router, prefix=api_prefix)
app.include_router(conversation_router, prefix=api_prefix)

# Mount Views Router
app.include_router(views_router)

# Mount static frontend directories
frontend_dir = os.path.join(BASE_DIR, "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")
    css_dir = os.path.join(frontend_dir, "css")
    js_dir = os.path.join(frontend_dir, "js")
    if os.path.exists(css_dir):
        app.mount("/css", StaticFiles(directory=css_dir), name="css")
    if os.path.exists(js_dir):
        app.mount("/js", StaticFiles(directory=js_dir), name="js")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
