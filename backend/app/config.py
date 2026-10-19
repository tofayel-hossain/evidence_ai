import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load .env file explicitly
env_path = BASE_DIR / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

# Ensure HF local cache is used immediately without network stalling
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
    class Settings(BaseSettings):
        PROJECT_NAME: str = os.getenv("PROJECT_NAME", "EvidenceAI")
        ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
        DEBUG: bool = os.getenv("DEBUG", "True").lower() in ("true", "1")
        API_V1_STR: str = os.getenv("API_V1_STR", "/api/v1")

        DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./evidenceai.db")

        SECRET_KEY: str = os.getenv("SECRET_KEY", "evidenceai-dev-secret-key-super-secure-2026")
        ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
        ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

        UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", str(BASE_DIR / "data" / "uploads"))
        INDEX_DIR: str = os.getenv("INDEX_DIR", str(BASE_DIR / "data" / "indices"))
        MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "25"))
        ALLOWED_EXTENSIONS: str = "pdf"

        EMBEDDING_MODEL_NAME: str = os.getenv("EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
        NLI_MODEL_NAME: str = os.getenv("NLI_MODEL_NAME", "cross-encoder/nli-deberta-v3-small")
        FAST_VERIFICATION: bool = os.getenv("FAST_VERIFICATION", "True").lower() in ("true", "1")

        DEFAULT_CHUNK_SIZE: int = int(os.getenv("DEFAULT_CHUNK_SIZE", "500"))
        DEFAULT_CHUNK_OVERLAP: int = int(os.getenv("DEFAULT_CHUNK_OVERLAP", "100"))
        RETRIEVAL_TOP_K: int = int(os.getenv("RETRIEVAL_TOP_K", "5"))
        HYBRID_ALPHA: float = float(os.getenv("HYBRID_ALPHA", "0.5"))

        LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "fallback")
        GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
        OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
        OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        LLM_MODEL_NAME: str = os.getenv("LLM_MODEL_NAME", "qwen/qwen3.8-27b")

        model_config = SettingsConfigDict(
            env_file=str(env_path),
            env_file_encoding="utf-8",
            extra="ignore"
        )
except ImportError:
    from pydantic import BaseModel
    class Settings(BaseModel):
        PROJECT_NAME: str = os.getenv("PROJECT_NAME", "EvidenceAI")
        ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
        DEBUG: bool = os.getenv("DEBUG", "True").lower() in ("true", "1")
        API_V1_STR: str = os.getenv("API_V1_STR", "/api/v1")

        DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./evidenceai.db")

        SECRET_KEY: str = os.getenv("SECRET_KEY", "evidenceai-dev-secret-key-super-secure-2026")
        ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
        ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

        UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", str(BASE_DIR / "data" / "uploads"))
        INDEX_DIR: str = os.getenv("INDEX_DIR", str(BASE_DIR / "data" / "indices"))
        MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "25"))
        ALLOWED_EXTENSIONS: str = "pdf"

        EMBEDDING_MODEL_NAME: str = os.getenv("EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
        NLI_MODEL_NAME: str = os.getenv("NLI_MODEL_NAME", "cross-encoder/nli-deberta-v3-small")
        FAST_VERIFICATION: bool = os.getenv("FAST_VERIFICATION", "True").lower() in ("true", "1")

        DEFAULT_CHUNK_SIZE: int = int(os.getenv("DEFAULT_CHUNK_SIZE", "500"))
        DEFAULT_CHUNK_OVERLAP: int = int(os.getenv("DEFAULT_CHUNK_OVERLAP", "100"))
        RETRIEVAL_TOP_K: int = int(os.getenv("RETRIEVAL_TOP_K", "5"))
        HYBRID_ALPHA: float = float(os.getenv("HYBRID_ALPHA", "0.5"))

        LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "fallback")
        GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
        OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
        OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        LLM_MODEL_NAME: str = os.getenv("LLM_MODEL_NAME", "qwen/qwen3.8-27b")

settings = Settings()

# Ensure directories exist
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.INDEX_DIR, exist_ok=True)
