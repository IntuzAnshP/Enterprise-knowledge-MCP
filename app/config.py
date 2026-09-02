from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

class Settings(BaseSettings):
    DATABASE_URL: str
    UPLOAD_DIR: Path = Path("./uploads")
    MAX_FILE_SIZE_MB: int = 50

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
