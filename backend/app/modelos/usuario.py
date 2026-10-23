from sqlalchemy import Boolean, CheckConstraint, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.modelos.comum import ChaveUuid, CriadoEm
from app.nucleo.banco import Base


class Usuario(ChaveUuid, CriadoEm, Base):
    __tablename__ = "usuarios"
    __table_args__ = (CheckConstraint("email = lower(email)", name="email_minusculo"),)

    nome_usuario: Mapped[str] = mapped_column(String(64), unique=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    senha_hash: Mapped[str] = mapped_column(Text)
    idioma: Mapped[str] = mapped_column(String(10), default="pt-BR", server_default="pt-BR")
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
