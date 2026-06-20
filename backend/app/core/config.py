import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://opsmind:change_me@127.0.0.1:5433/opsmind",
)

SECRET_KEY = os.getenv("SECRET_KEY", "change_me_in_local_dev")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

_upload_storage_dir = Path(os.getenv("UPLOAD_STORAGE_DIR", "backend/storage/uploads"))
UPLOAD_STORAGE_DIR = _upload_storage_dir if _upload_storage_dir.is_absolute() else PROJECT_ROOT / _upload_storage_dir
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(20 * 1024 * 1024)))

CHROMA_HOST = os.getenv("CHROMA_HOST", "127.0.0.1")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8001"))
CHROMA_DOCUMENT_COLLECTION = os.getenv("CHROMA_DOCUMENT_COLLECTION", "opsmind_documents")

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "fake").strip().lower()
LLM_MODEL = os.getenv("LLM_MODEL", "opsmind-fake").strip()
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "").strip() or None
LLM_API_KEY = os.getenv("LLM_API_KEY", "").strip() or None
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "60"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))
LLM_MAX_OUTPUT_TOKENS = int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "1200"))
