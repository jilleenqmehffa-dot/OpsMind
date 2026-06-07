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
