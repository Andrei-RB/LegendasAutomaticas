import os
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.nucleo.config_auth import ConfigAuth as Settings

RAIZ_BACKEND = Path(__file__).resolve().parents[1]
SEGREDO_32 = "k" * 32


@pytest.fixture(autouse=True)
def _ambiente_limpo(monkeypatch):
    for nome in ("JWT_SECRET", "JWT_EXPIRA_MINUTOS", "COOKIE_SECURE", "PERMITIR_CADASTRO"):
        monkeypatch.delenv(nome, raising=False)


def _criar(**campos) -> Settings:
    return Settings(_env_file=None, **campos)


def test_jwt_secret_ausente_levanta_validation_error():
    with pytest.raises(ValidationError) as erro:
        _criar()

    assert "JWT_SECRET" in str(erro.value)


def test_jwt_secret_com_31_bytes_e_recusado():
    with pytest.raises(ValidationError):
        _criar(JWT_SECRET="k" * 31)


def test_jwt_secret_com_32_bytes_e_aceito():
    assert _criar(JWT_SECRET=SEGREDO_32).JWT_SECRET.get_secret_value() == SEGREDO_32


def test_jwt_secret_conta_bytes_e_nao_caracteres():
    assert _criar(JWT_SECRET="á" * 16)
    with pytest.raises(ValidationError):
        _criar(JWT_SECRET="á" * 15 + "a")


def test_jwt_secret_vazio_e_recusado():
    with pytest.raises(ValidationError):
        _criar(JWT_SECRET="")


def test_jwt_secret_lido_do_ambiente(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SEGREDO_32)

    assert _criar().JWT_SECRET.get_secret_value() == SEGREDO_32


def test_padroes_de_autenticacao():
    configuracao = _criar(JWT_SECRET=SEGREDO_32)

    assert configuracao.JWT_EXPIRA_MINUTOS == 480
    assert configuracao.COOKIE_SECURE is True
    assert configuracao.PERMITIR_CADASTRO is False


def test_valores_de_autenticacao_vindos_do_ambiente(monkeypatch):
    monkeypatch.setenv("JWT_EXPIRA_MINUTOS", "15")
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setenv("PERMITIR_CADASTRO", "true")

    configuracao = _criar(JWT_SECRET=SEGREDO_32)

    assert configuracao.JWT_EXPIRA_MINUTOS == 15
    assert configuracao.COOKIE_SECURE is False
    assert configuracao.PERMITIR_CADASTRO is True


def test_segredo_nao_aparece_em_repr_str_nem_dump():
    segredo = "segredo-que-nao-pode-vazar-" + "z" * 16
    configuracao = _criar(JWT_SECRET=segredo)

    assert configuracao.JWT_SECRET.get_secret_value() == segredo
    assert segredo not in repr(configuracao)
    assert segredo not in str(configuracao)
    assert segredo not in configuracao.model_dump_json()
    assert segredo not in repr(configuracao.model_dump())


def _importar_app_main(env_extra: dict[str, str], pasta: Path) -> subprocess.CompletedProcess:
    env = {
        chave: valor
        for chave, valor in os.environ.items()
        if chave in ("PATH", "SYSTEMROOT", "TEMP", "TMP", "TMPDIR", "HOME", "USERPROFILE")
    }
    env.update(
        PYTHONPATH=str(RAIZ_BACKEND),
        UPLOAD_DIR=str(pasta / "up"),
        OUTPUT_DIR=str(pasta / "out"),
        LOG_DIR=str(pasta / "log"),
        **env_extra,
    )
    return subprocess.run(  # noqa: S603
        [sys.executable, "-c", "import app.main"],
        cwd=pasta,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def test_importar_app_main_sem_jwt_secret_falha(tmp_path):
    resultado = _importar_app_main({}, tmp_path)

    assert resultado.returncode != 0
    assert "JWT_SECRET" in resultado.stderr


def test_importar_app_main_com_jwt_secret_curto_falha(tmp_path):
    resultado = _importar_app_main({"JWT_SECRET": "k" * 31}, tmp_path)

    assert resultado.returncode != 0
    assert "JWT_SECRET" in resultado.stderr


def test_importar_app_main_com_jwt_secret_valido_funciona(tmp_path):
    resultado = _importar_app_main({"JWT_SECRET": SEGREDO_32}, tmp_path)

    assert resultado.returncode == 0, resultado.stderr
    assert SEGREDO_32 not in resultado.stderr
