import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String, Text, UniqueConstraint, Uuid, func
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


class TextoPostagem(ChaveUuid, CriadoEm, DonoObrigatorio, Base):
    __tablename__ = "textos_postagem"
    __table_args__ = (fk_dono("corte_id", "cortes"),)

    corte_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    plataforma: Mapped[str] = mapped_column(String(16))
    titulo: Mapped[str | None] = mapped_column(Text)
    descricao: Mapped[str | None] = mapped_column(Text)
    hashtags: Mapped[list[Any]] = coluna_jsonb(list)
    tags: Mapped[list[Any]] = coluna_jsonb(list)
    capitulos: Mapped[list[Any]] = coluna_jsonb(list)


class CacheHashtags(ChaveUuid, Base):
    """Compartilhado por nicho e plataforma; não pertence a um usuário."""

    __tablename__ = "cache_hashtags"
    __table_args__ = (UniqueConstraint("nicho", "plataforma"),)

    nicho: Mapped[str] = mapped_column(String(64))
    plataforma: Mapped[str] = mapped_column(String(16))
    hashtags: Mapped[list[Any]] = coluna_jsonb(list)
    buscado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=agora_utc, server_default=func.now()
    )


class HashtagUsuario(ChaveUuid, CriadoEm, DonoObrigatorio, Base):
    __tablename__ = "hashtags_usuario"
    __table_args__ = (UniqueConstraint("user_id", "hashtag"),)

    hashtag: Mapped[str] = mapped_column(String(64))
