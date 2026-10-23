import re

from psycopg import Connection, sql
from sqlalchemy import Engine, create_engine
from sqlalchemy.pool import NullPool

from app.nucleo.banco import normalizar_url

PAPEL_APP = "viraliza_app"
TABELA_VERSAO = "alembic_version"
TAMANHO_MINIMO_SENHA = 16
_PADRAO_PAPEL = re.compile(r"[a-z_][a-z0-9_]{0,62}")
_DML = sql.SQL("SELECT, INSERT, UPDATE, DELETE")


def _motor_dono(url: str) -> Engine:
    return create_engine(
        normalizar_url(url),
        poolclass=NullPool,
        isolation_level="AUTOCOMMIT",
        connect_args={"connect_timeout": 10},
        hide_parameters=True,
    )


def validar_senha(senha: str) -> None:
    if len(senha) < TAMANHO_MINIMO_SENHA:
        raise ValueError(f"a senha do papel deve ter ao menos {TAMANHO_MINIMO_SENHA} caracteres")


def aplicar_papel_app(url_dono: str, senha: str, *, papel: str = PAPEL_APP) -> None:
    """Cria ou atualiza o papel da aplicação (só DML); idempotente e executado pelo dono."""
    if not _PADRAO_PAPEL.fullmatch(papel):
        raise ValueError("nome de papel inválido")
    validar_senha(senha)

    motor = _motor_dono(url_dono)
    try:
        with motor.connect() as ligacao:
            _aplicar(ligacao.connection.driver_connection, papel, senha)
    finally:
        motor.dispose()


def _hash_scram(conexao: Connection, papel: str, senha: str) -> str:
    """Evita enviar a senha em texto claro (visível em log e em pg_stat_activity)."""
    return conexao.pgconn.encrypt_password(
        senha.encode(), papel.encode(), b"scram-sha-256"
    ).decode()


def _aplicar(conexao: Connection, papel: str, senha: str) -> None:
    nome = sql.Identifier(papel)
    if not conexao.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (papel,)).fetchone():
        conexao.execute(sql.SQL("CREATE ROLE {}").format(nome))
    conexao.execute(
        sql.SQL(
            "ALTER ROLE {} WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION "
            "NOBYPASSRLS PASSWORD {}"
        ).format(nome, sql.Literal(_hash_scram(conexao, papel, senha)))
    )

    banco = sql.Identifier(conexao.execute("SELECT current_database()").fetchone()[0])
    dono = sql.Identifier(conexao.execute("SELECT current_user").fetchone()[0])
    comandos = [
        sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(banco),
        sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(banco, nome),
        sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(nome),
        sql.SQL("GRANT {} ON ALL TABLES IN SCHEMA public TO {}").format(_DML, nome),
        sql.SQL(
            "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public GRANT {} ON TABLES TO {}"
        ).format(dono, _DML, nome),
    ]
    for comando in comandos:
        conexao.execute(comando)

    versao = f"public.{TABELA_VERSAO}"
    if conexao.execute("SELECT to_regclass(%s) IS NOT NULL", (versao,)).fetchone()[0]:
        conexao.execute(
            sql.SQL("REVOKE ALL ON TABLE {} FROM {}").format(sql.Identifier(TABELA_VERSAO), nome)
        )
