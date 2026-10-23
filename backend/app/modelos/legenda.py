import uuid
from typing import Any

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.modelos.comum import (
    ChaveUuid,
    CriadoEm,
    DonoObrigatorio,
    DonoOpcional,
    coluna_jsonb,
    fk_dono,
)
from app.nucleo.banco import Base


class DocumentoLegenda(ChaveUuid, CriadoEm, DonoObrigatorio, Base):
    __tablename__ = "documentos_legenda"
    __table_args__ = (
        UniqueConstraint("id", "user_id"),
        UniqueConstraint("corte_id", "versao"),
        fk_dono("corte_id", "cortes"),
    )

    corte_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    versao: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    conteudo: Mapped[dict[str, Any]] = coluna_jsonb(inicial=False)


class ModeloLegenda(ChaveUuid, CriadoEm, DonoOpcional, Base):
    __tablename__ = "modelos_legenda"

    nome: Mapped[str] = mapped_column(String(64))
    versao_schema: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    especificacao: Mapped[dict[str, Any]] = coluna_jsonb(inicial=False)


class Fonte(ChaveUuid, CriadoEm, DonoOpcional, Base):
    __tablename__ = "fontes"

    familia: Mapped[str] = mapped_column(String(64))
    origem: Mapped[str] = mapped_column(String(16))
    caminho: Mapped[str] = mapped_column(Text)
    licenca: Mapped[str | None] = mapped_column(String(64))


class Exportacao(ChaveUuid, CriadoEm, DonoObrigatorio, Base):
    """O dono de `modelo_legenda_id` é validado por gatilho (`ck_exportacoes_modelo_dono`)."""

    __tablename__ = "exportacoes"
    __table_args__ = (
        fk_dono("corte_id", "cortes"),
        fk_dono("documento_legenda_id", "documentos_legenda", opcional=True),
    )

    corte_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    modelo_legenda_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("modelos_legenda.id", ondelete="SET NULL"), index=True
    )
    documento_legenda_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    caminhos_srt: Mapped[dict[str, Any]] = coluna_jsonb()
    caminho_mp4: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="pendente", server_default="pendente")
