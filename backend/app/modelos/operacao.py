import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, Integer, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.modelos.comum import ChaveUuid, CriadoEm, DonoObrigatorio, coluna_jsonb, fk_dono
from app.nucleo.banco import Base


class ChamadaIa(ChaveUuid, CriadoEm, DonoObrigatorio, Base):
    __tablename__ = "chamadas_ia"
    __table_args__ = (fk_dono("analise_id", "analises", opcional=True),)

    analise_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    tarefa: Mapped[str] = mapped_column(String(32))
    provedor: Mapped[str] = mapped_column(String(32))
    modelo: Mapped[str] = mapped_column(String(64))
    tokens_entrada: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    tokens_saida: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    custo_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=0, server_default="0")
    latencia_ms: Mapped[int | None] = mapped_column(Integer)
    cache: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    status: Mapped[str] = mapped_column(String(16))


class Feedback(ChaveUuid, CriadoEm, DonoObrigatorio, Base):
    """Sobrevive à expiração do corte; `instantaneo` guarda os dados usados no aprendizado."""

    __tablename__ = "feedback"
    __table_args__ = (
        fk_dono("corte_id", "cortes", opcional=True),
        fk_dono("candidato_id", "candidatos", opcional=True),
    )

    corte_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    candidato_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    aprovado: Mapped[bool] = mapped_column(Boolean)
    motivo: Mapped[str | None] = mapped_column(Text)
    instantaneo: Mapped[dict[str, Any]] = coluna_jsonb()
