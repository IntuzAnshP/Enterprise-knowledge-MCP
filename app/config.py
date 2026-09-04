from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
import os

# Base directory (Enterprise-mcp)
BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    DATABASE_URL: str
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    MAX_FILE_SIZE_MB: int = 50
    ENABLE_RERANKER: bool = False
    RERANKER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    RETRIEVAL_TOP_K: int = 20
    RETRIEVAL_FINAL_K: int = 5

    # ── Google Drive Connector (Phase 4) ────────────────────────────────────
    # Path to the service account JSON credentials file
    GOOGLE_DRIVE_CREDENTIALS_JSON: str = ""
    # Root Google Drive folder ID to watch (share this folder with the service account)
    GOOGLE_DRIVE_FOLDER_ID: str = ""
    # How often the background scheduler runs a sync (in minutes)
    GOOGLE_DRIVE_SYNC_INTERVAL_MINUTES: int = 30
    # Local directory where Drive files are downloaded before parsing
    GOOGLE_DRIVE_DOWNLOAD_DIR: Path = BASE_DIR / "downloads" / "google_drive"

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"), 
        env_file_encoding="utf-8"
    )

settings = Settings()

