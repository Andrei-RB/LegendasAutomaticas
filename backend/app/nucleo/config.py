import os

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

    APP_NAME: str = "Secure Subtitle Generator"
    APP_ENV: str = "production"
    DEBUG: bool = False
    API_V1_STR: str = "/api/v1"

    REDIS_URL: str = "redis://localhost:6379/0"
    DATABASE_URL: SecretStr = SecretStr("")
    SENHA_PAPEL_APP: SecretStr = SecretStr("")

    UPLOAD_DIR: str = "uploads"
    OUTPUT_DIR: str = "outputs"
    LOG_DIR: str = "logs"

    DADOS_DIR: str = "dados"

    SSE_HEARTBEAT_S: float = Field(default=15, gt=0)
    SSE_DURACAO_MAX_S: float = Field(default=5400, gt=0)
    SSE_MAX_POR_USUARIO: int = Field(default=5, ge=1)
    SSE_MAX_GLOBAL: int = Field(default=50, ge=1)

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
