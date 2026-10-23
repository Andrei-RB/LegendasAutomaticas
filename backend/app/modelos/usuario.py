from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.modelos.comum import ChaveUuid, CriadoEm
from app.nucleo.banco import Base


class Usuario(ChaveUuid, CriadoEm, Base):
    __tablename__ = "usuarios"

    nome_usuario: Mapped[str] = mapped_column(String(64), unique=True)
    idioma: Mapped[str] = mapped_column(String(10), default="pt-BR", server_default="pt-BR")
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
