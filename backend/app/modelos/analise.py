import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.modelos.comum import (
    ChaveUuid,
    CriadoEm,
    DonoObrigatorio,
    agora_utc,
    coluna_jsonb,
    fk_dono,
)
from app.nucleo.banco import Base


class Analise(ChaveUuid, CriadoEm, DonoObrigatorio, Base):
    __tablename__ = "analises"
    __table_args__ = (
        UniqueConstraint("id", "user_id"),
        fk_dono("video_id", "videos"),
        CheckConstraint("progresso >= 0 AND progresso <= 100", name="progresso_faixa"),
    )

    video_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    parametros: Mapped[dict[str, Any]] = coluna_jsonb(inicial=False)
    status: Mapped[str] = mapped_column(String(16), default="pendente", server_default="pendente")
    etapa_atual: Mapped[str | None] = mapped_column(String(32))
    progresso: Mapped[float] = mapped_column(Float, default=0, server_default="0")
    erro_amigavel: Mapped[str | None] = mapped_column(Text)
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=agora_utc, onupdate=agora_utc, server_default=func.now()
    )


class ExecucaoEtapa(ChaveUuid, CriadoEm, DonoObrigatorio, Base):
    __tablename__ = "execucoes_etapa"
    __table_args__ = (
        UniqueConstraint("analise_id", "etapa", "hash_entrada"),
        fk_dono("analise_id", "analises"),
    )

    analise_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    etapa: Mapped[str] = mapped_column(String(32))
    hash_entrada: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="pendente", server_default="pendente")
    artefatos: Mapped[dict[str, Any]] = coluna_jsonb()
    metricas: Mapped[dict[str, Any]] = coluna_jsonb()
    iniciado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    concluido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
