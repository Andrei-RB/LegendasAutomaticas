import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ_BACKEND = Path(__file__).resolve().parents[2]
PROIBIDOS = ("app.nucleo.config_auth", "app.nucleo.dependencias")
ROTULO = "MODULOS_CARREGADOS="


def _executar(importacoes: list[str], pasta: Path, *, com_jwt: bool = False):
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
    )
    if com_jwt:
        env["JWT_SECRET"] = "segredo-jwt-apenas-para-testes-" + "0123456789abcdef" * 3
    codigo = (
        "import sys, json\n"
        + "".join(f"import {nome}\n" for nome in importacoes)
        + f"print({ROTULO!r} + json.dumps(sorted(sys.modules)))\n"
    )
    return subprocess.run(  # noqa: S603
        [sys.executable, "-c", codigo],
        cwd=pasta,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )


def _modulos(resultado: subprocess.CompletedProcess) -> set[str]:
    linhas = [ln for ln in resultado.stdout.splitlines() if ln.startswith(ROTULO)]
    assert linhas, resultado.stderr[-2000:]
    return set(json.loads(linhas[-1][len(ROTULO) :]))


def test_controle_app_main_carrega_modulos_de_autenticacao(tmp_path):
    resultado = _executar(["app.main"], tmp_path, com_jwt=True)

    assert resultado.returncode == 0, resultado.stderr[-2000:]
    carregados = _modulos(resultado)
    assert set(PROIBIDOS) <= carregados


def test_importacao_conjunta_dos_modulos_do_worker_sem_jwt_secret(tmp_path):
    resultado = _executar(
        ["app.workers.celery_app", "app.pipeline.tarefas", "app.pipeline.executor"], tmp_path
    )

    assert resultado.returncode == 0, resultado.stderr[-2000:]
    carregados = _modulos(resultado)
    assert "app.pipeline.executor" in carregados
    assert "app.pipeline.tarefas" in carregados
    for proibido in PROIBIDOS:
        assert proibido not in carregados


@pytest.mark.parametrize(
    "modulo",
    [
        "app.pipeline.hashing",
        "app.pipeline.armazenamento",
        "app.pipeline.trava_gpu",
        "app.pipeline.erros",
        "app.pipeline.eventos",
        "app.pipeline.executor",
        "app.pipeline.registro",
        "app.pipeline.etapas.exemplo",
        "app.pipeline.tarefas",
        "app.workers.celery_app",
    ],
)
def test_modulo_isolado_nao_carrega_autenticacao_nem_exige_jwt_secret(tmp_path, modulo):
    resultado = _executar([modulo], tmp_path)

    assert resultado.returncode == 0, resultado.stderr[-2000:]
    carregados = _modulos(resultado)
    assert modulo in carregados
    for proibido in PROIBIDOS:
        assert proibido not in carregados
