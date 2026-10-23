import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import DateTime, ForeignKey, ForeignKeyConstraint, Uuid, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import Mapped, MappedColumn, mapped_column

RETENCAO_VIDEO_DIAS = 7
RETENCAO_CORTE_DIAS = 30


def agora_utc() -> datetime:
    return datetime.now(UTC)


def expira_video() -> datetime:
    return agora_utc() + timedelta(days=RETENCAO_VIDEO_DIAS)


def expira_corte() -> datetime:
    return agora_utc() + timedelta(days=RETENCAO_CORTE_DIAS)


class ChaveUuid:
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )


class CriadoEm:
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=agora_utc, server_default=func.now()
    )


class DonoObrigatorio:
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), index=True
    )


class DonoOpcional:
    """`user_id` nulo identifica registro de sistema."""

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), index=True
    )


def fk_dono(coluna: str, pai: str, *, opcional: bool = False) -> ForeignKeyConstraint:
    """FK composta que amarra o `user_id` da filha ao do pai; `opcional` zera só a coluna."""
    ondelete = f"SET NULL ({coluna})" if opcional else "CASCADE"
    return ForeignKeyConstraint(
        [coluna, "user_id"], [f"{pai}.id", f"{pai}.user_id"], ondelete=ondelete
    )


def coluna_jsonb(
    tipo: type[dict] | type[list] = dict, *, inicial: bool = True
) -> MappedColumn[Any]:
    """JSONB mutável; com `inicial`, usa `{}` ou `[]` como valor padrão."""
    mutavel = MutableDict if tipo is dict else MutableList
    coluna = mutavel.as_mutable(JSONB)
    if not inicial:
        return mapped_column(coluna)
    literal = "'{}'::jsonb" if tipo is dict else "'[]'::jsonb"
    return mapped_column(coluna, default=tipo, server_default=text(literal))
