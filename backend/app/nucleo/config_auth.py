from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

TAMANHO_MINIMO_SEGREDO = 32


class ConfigAuth(BaseSettings):
    """Configuração de sessão; separada de `Settings` para os workers não receberem o segredo."""

    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=True, extra="ignore", hide_input_in_errors=True
    )

    JWT_SECRET: SecretStr
    JWT_EXPIRA_MINUTOS: int = Field(default=480, ge=1, le=1440)
    COOKIE_SECURE: bool = True
    PERMITIR_CADASTRO: bool = False

    @field_validator("JWT_SECRET")
    @classmethod
    def _segredo_forte(cls, valor: SecretStr) -> SecretStr:
        if len(valor.get_secret_value().encode()) < TAMANHO_MINIMO_SEGREDO:
            raise ValueError(f"JWT_SECRET deve ter ao menos {TAMANHO_MINIMO_SEGREDO} bytes")
        return valor


config_auth = ConfigAuth()
