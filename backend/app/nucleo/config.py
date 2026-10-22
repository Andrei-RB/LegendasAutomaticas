import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

    APP_NAME: str = "Secure Subtitle Generator"
    APP_ENV: str = "production"
    DEBUG: bool = False
    API_V1_STR: str = "/api/v1"

    REDIS_URL: str = "redis://localhost:6379/0"

    UPLOAD_DIR: str = "uploads"
    OUTPUT_DIR: str = "outputs"
    LOG_DIR: str = "logs"

    MAX_UPLOAD_SIZE: int = 1024 * 1024 * 1024
    ALLOWED_EXTENSIONS: str = ".mp4,.avi,.mov,.mkv"
    FFMPEG_TIMEOUT_S: int = 1800

    # Origens extras separadas por vírgula; a lista fixa local só vale fora de produção.
    CORS_ORIGINS: str = ""

    @property
    def allowed_extensions_list(self) -> list[str]:
        return [ext.strip() for ext in self.ALLOWED_EXTENSIONS.split(",") if ext.strip()]


settings = Settings()

for _diretorio in (settings.UPLOAD_DIR, settings.OUTPUT_DIR, settings.LOG_DIR):
    os.makedirs(_diretorio, exist_ok=True)
