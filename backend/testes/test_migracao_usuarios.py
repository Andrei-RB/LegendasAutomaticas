import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from alembic import command
from app.nucleo.papeis import aplicar_papel_app

SENHA_PAPEL = "senha-do-papel-0123456789"
HASH = "$argon2id$hash-de-teste"


def _colunas(url: str) -> dict[str, dict]:
    motor = create_engine(url)
    try:
        return {c["name"]: c for c in sa_inspect(motor).get_columns("usuarios")}
    finally:
        motor.dispose()


def _unicos(url: str) -> list[list[str]]:
    motor = create_engine(url)
    try:
        inspetor = sa_inspect(motor)
        restricoes = [u["column_names"] for u in inspetor.get_unique_constraints("usuarios")]
        indices = [i["column_names"] for i in inspetor.get_indexes("usuarios") if i["unique"]]
        return restricoes + indices
    finally:
        motor.dispose()


def test_usuarios_tem_email_e_senha_hash_obrigatorios(banco_migrado):
    colunas = _colunas(banco_migrado)

    assert colunas["email"]["nullable"] is False
    assert colunas["senha_hash"]["nullable"] is False
    assert "nome_usuario" in colunas


def test_email_e_unico(banco_migrado):
    assert ["email"] in _unicos(banco_migrado)

    motor = create_engine(banco_migrado)
    try:
        with motor.begin() as con:
            con.execute(
                text(
                    "INSERT INTO usuarios (nome_usuario, email, senha_hash) "
                    "VALUES ('a', 'a@exemplo.com', :h)"
                ),
                {"h": HASH},
            )
        with pytest.raises(IntegrityError), motor.begin() as con:
            con.execute(
                text(
                    "INSERT INTO usuarios (nome_usuario, email, senha_hash) "
                    "VALUES ('b', 'a@exemplo.com', :h)"
                ),
                {"h": HASH},
            )
    finally:
        motor.dispose()


def test_usuario_sem_email_ou_sem_hash_e_recusado(banco_migrado):
    motor = create_engine(banco_migrado)
    try:
        for comando in (
            "INSERT INTO usuarios (nome_usuario, senha_hash) VALUES ('x', 'h')",
            "INSERT INTO usuarios (nome_usuario, email) VALUES ('x', 'x@exemplo.com')",
        ):
            with pytest.raises(IntegrityError), motor.begin() as con:
                con.execute(text(comando))
    finally:
        motor.dispose()


def test_alembic_check_limpo_apos_upgrade(banco_migrado, config_alembic):
    command.check(config_alembic(banco_migrado))


def test_downgrade_e_upgrade_repetem_sem_erro(banco_limpo, config_alembic):
    cfg = config_alembic(banco_limpo)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "0001")
    assert "email" not in _colunas(banco_limpo)
    command.upgrade(cfg, "head")

    assert {"email", "senha_hash"} <= set(_colunas(banco_limpo))


def test_papel_da_aplicacao_faz_insert_select_update_nas_novas_colunas(banco_migrado):
    papel = f"viraliza_app_t_{uuid.uuid4().hex[:8]}"
    aplicar_papel_app(banco_migrado, SENHA_PAPEL, papel=papel)
    url_papel = make_url(banco_migrado).set(username=papel, password=SENHA_PAPEL)
    motor = create_engine(url_papel, isolation_level="AUTOCOMMIT")
    try:
        with motor.connect() as con:
            con.execute(
                text(
                    "INSERT INTO usuarios (nome_usuario, email, senha_hash) "
                    "VALUES ('a', 'a@exemplo.com', :h)"
                ),
                {"h": HASH},
            )
            assert con.execute(text("SELECT email, senha_hash FROM usuarios")).all() == [
                ("a@exemplo.com", HASH)
            ]
            atualizadas = con.execute(
                text("UPDATE usuarios SET email = 'b@exemplo.com', senha_hash = 'novo'")
            ).rowcount
            assert atualizadas == 1
            assert con.execute(text("SELECT email FROM usuarios")).scalar_one() == "b@exemplo.com"
    finally:
        motor.dispose()
        limpar = create_engine(banco_migrado, isolation_level="AUTOCOMMIT")
        with limpar.connect() as con:
            con.execute(text(f'DROP OWNED BY "{papel}"'))
            con.execute(text(f'DROP ROLE "{papel}"'))
        limpar.dispose()
