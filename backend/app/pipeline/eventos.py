import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from redis import Redis
from redis.exceptions import RedisError

from app.nucleo.logger import logger
from app.pipeline.erros import MENSAGENS

TipoEvento = Literal["etapa_iniciada", "passo_concluido", "etapa_concluida", "etapa_pulada", "erro"]


def canal(user_id: uuid.UUID, analise_id: uuid.UUID) -> str:
    return f"eventos:{user_id}:{analise_id}"


class EventoAnalise(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tipo: TipoEvento
    analise_id: uuid.UUID
    etapa: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]{0,31}$")
    passo: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]{0,31}$")
    progresso_etapa: float = Field(default=0, ge=0, le=100, allow_inf_nan=False)
    codigo: str | None = None
    mensagem: str | None = Field(default=None, max_length=200)
    emitido_em: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("codigo")
    @classmethod
    def _codigo_do_catalogo(cls, valor: str | None) -> str | None:
        if valor is not None and valor not in MENSAGENS:
            raise ValueError("código fora do catálogo de erros")
        return valor

    def to_json(self) -> str:
        # O JSON escapa quebras de linha, o que mantém o evento em uma única linha SSE.
        return self.model_dump_json()


class PublicadorEventos:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    def publicar(self, user_id: uuid.UUID, evento: EventoAnalise) -> None:
        try:
            self._redis.publish(canal(user_id, evento.analise_id), evento.to_json())
        except RedisError as erro:
            # O progresso é informativo: falha no pub/sub não interrompe o pipeline.
            logger.warning(f"Evento não publicado: {type(erro).__name__}")
