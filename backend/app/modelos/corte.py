import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.modelos.comum import (
    RETENCAO_CORTE_DIAS,
    ChaveUuid,
    CriadoEm,
    DonoObrigatorio,
    coluna_jsonb,
    expira_corte,
    fk_dono,
)
from app.nucleo.banco import Base


class Candidato(ChaveUuid, CriadoEm, DonoObrigatorio, Base):
    __tablename__ = "candidatos"
    __table_args__ = (
        UniqueConstraint("id", "user_id"),
        fk_dono("analise_id", "analises"),
        CheckConstraint("fim_s > inicio_s", name="intervalo_valido"),
    )

    analise_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    inicio_s: Mapped[float] = mapped_column(Float)
    fim_s: Mapped[float] = mapped_column(Float)
    id_frase_inicial: Mapped[int] = mapped_column(Integer)
    id_frase_final: Mapped[int] = mapped_column(Integer)
    variantes: Mapped[list[Any]] = coluna_jsonb(list)
    nota_heuristica: Mapped[float | None] = mapped_column(Float)
    features: Mapped[dict[str, Any]] = coluna_jsonb()


class Julgamento(ChaveUuid, CriadoEm, DonoObrigatorio, Base):
    __tablename__ = "julgamentos"
    __table_args__ = (fk_dono("candidato_id", "candidatos"),)

    candidato_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    juiz: Mapped[str] = mapped_column(String(32))
    modelo: Mapped[str] = mapped_column(String(64))
    versao_prompt: Mapped[str] = mapped_column(String(16))
    notas: Mapped[dict[str, Any]] = coluna_jsonb()
    motivo: Mapped[str | None] = mapped_column(Text)
    citacoes: Mapped[list[Any]] = coluna_jsonb(list)
    valido: Mapped[bool] = mapped_column(Boolean)


class Corte(ChaveUuid, CriadoEm, DonoObrigatorio, Base):
    __tablename__ = "cortes"
    __table_args__ = (
        UniqueConstraint("id", "user_id"),
        fk_dono("analise_id", "analises"),
        fk_dono("candidato_id", "candidatos", opcional=True),
        CheckConstraint("fim_s > inicio_s", name="intervalo_valido"),
    )

    analise_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    candidato_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    inicio_s: Mapped[float] = mapped_column(Float)
    fim_s: Mapped[float] = mapped_column(Float)
    formato: Mapped[str] = mapped_column(String(16), default="9:16", server_default="9:16")
    keyframes_camera: Mapped[list[Any]] = coluna_jsonb(list)
    caminho_previa: Mapped[str | None] = mapped_column(Text)
    caminho_final: Mapped[str | None] = mapped_column(Text)
    expira_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=expira_corte,
        server_default=text(f"now() + interval '{RETENCAO_CORTE_DIAS} days'"),
    )
