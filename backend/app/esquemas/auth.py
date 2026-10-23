import uuid

from email_validator import EmailNotValidError, validate_email
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.nucleo.autenticacao import SENHA_MAXIMO, validar_politica_senha


def _normalizar_email(valor: str) -> str:
    try:
        return validate_email(valor.strip(), check_deliverability=False).normalized.lower()
    except EmailNotValidError:
        raise ValueError("E-mail inválido.") from None


class _Estrito(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CadastroEntrada(_Estrito):
    email: str = Field(max_length=254)
    senha: str
    nome_usuario: str = Field(min_length=1, max_length=64)

    @field_validator("email")
    @classmethod
    def _email(cls, valor: str) -> str:
        return _normalizar_email(valor)

    @field_validator("senha")
    @classmethod
    def _senha(cls, valor: str) -> str:
        validar_politica_senha(valor)
        return valor

    @field_validator("nome_usuario")
    @classmethod
    def _nome(cls, valor: str) -> str:
        nome = valor.strip()
        if not nome:
            raise ValueError("Nome de usuário vazio.")
        return nome


class LoginEntrada(_Estrito):
    email: str = Field(max_length=254)
    senha: str = Field(min_length=1, max_length=SENHA_MAXIMO)

    @field_validator("email")
    @classmethod
    def _email(cls, valor: str) -> str:
        try:
            return _normalizar_email(valor)
        except ValueError:
            return valor.strip().lower()


class UsuarioSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    nome_usuario: str
    idioma: str
