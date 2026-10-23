"""Credenciais de usuário."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("usuarios", sa.Column("email", sa.String(length=254), nullable=False))
    op.add_column("usuarios", sa.Column("senha_hash", sa.Text(), nullable=False))
    op.create_unique_constraint(op.f("uq_usuarios_email"), "usuarios", ["email"])
    op.create_check_constraint(
        op.f("ck_usuarios_email_minusculo"), "usuarios", "email = lower(email)"
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_usuarios_email_minusculo"), "usuarios", type_="check")
    op.drop_constraint(op.f("uq_usuarios_email"), "usuarios", type_="unique")
    op.drop_column("usuarios", "senha_hash")
    op.drop_column("usuarios", "email")
