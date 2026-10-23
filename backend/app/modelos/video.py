from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.modelos.comum import (
    RETENCAO_VIDEO_DIAS,
    ChaveUuid,
    CriadoEm,
    DonoObrigatorio,
    coluna_jsonb,
    expira_video,
)
from app.nucleo.banco import Base


class Video(ChaveUuid, CriadoEm, DonoObrigatorio, Base):
    __tablename__ = "videos"
    __table_args__ = (UniqueConstraint("id", "user_id"),)

    origem: Mapped[str] = mapped_column(String(16))
    url_origem: Mapped[str | None] = mapped_column(Text)
    caminho_original: Mapped[str] = mapped_column(Text)
    caminho_proxy: Mapped[str | None] = mapped_column(Text)
    duracao_s: Mapped[float | None] = mapped_column(Float)
    metadados: Mapped[dict[str, Any]] = coluna_jsonb()
    perfil: Mapped[str | None] = mapped_column(String(32))
    expira_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=expira_video,
        server_default=text(f"now() + interval '{RETENCAO_VIDEO_DIAS} days'"),
    )
