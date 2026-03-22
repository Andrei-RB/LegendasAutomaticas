import os
from typing import List
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # App config
    APP_NAME: str = "Secure Subtitle Generator"
    APP_ENV: str = "production"
    DEBUG: bool = False
    API_V1_STR: str = "/api/v1"

    # Services
    REDIS_URL: str = "redis://localhost:6379/0"

    # Directories
    UPLOAD_DIR: str = "uploads"
    OUTPUT_DIR: str = "outputs"
    LOG_DIR: str = "logs"

    # Security Limits
    MAX_UPLOAD_SIZE: int = 1024 * 1024 * 1024  # default 1 GB
    ALLOWED_EXTENSIONS: str = ".mp4,.avi,.mov,.mkv"

    @property
    def allowed_extensions_list(self) -> List[str]:
        return [ext.strip() for ext in self.ALLOWED_EXTENSIONS.split(",")]

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()

# Ensure directories exist securely
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
os.makedirs(settings.LOG_DIR, exist_ok=True)
