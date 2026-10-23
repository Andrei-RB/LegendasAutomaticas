import os
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from app.nucleo.config import settings
from app.workers.tasks import process_video_task


@pytest.fixture
def fila_simulada(monkeypatch):
    """Evita o broker: registra o envio e simula o estado da tarefa como concluído."""
    enviados = []

    def _apply_async(args=None, task_id=None, **_):
        enviados.append((args, task_id))
        return SimpleNamespace(id=task_id)

    monkeypatch.setattr(process_video_task, "apply_async", _apply_async)
    monkeypatch.setattr(
        process_video_task,
        "AsyncResult",
        lambda _id: SimpleNamespace(
            state="SUCCESS", info={"progress": 100, "result_url": f"/api/v1/download/{_id}"}
        ),
    )
    return enviados


def _enviar(usuario) -> str:
    resposta = usuario.cliente.post(
        "/api/v1/upload-video", files={"file": ("video.mp4", b"conteudo", "video/mp4")}
    )
    assert resposta.status_code == 200, resposta.text
    return resposta.json()["job_id"]


def _gravar_srt(job_id: str) -> None:
    caminho = os.path.join(settings.OUTPUT_DIR, f"{job_id}.srt")
    with open(caminho, "w", encoding="utf-8") as arquivo:
        arquivo.write("1\n00:00:00,000 --> 00:00:01,000\nOlá\n\n")


def _linhas_video(ambiente, job_id: str, user_id: str):
    with ambiente.motor.connect() as con:
        return con.execute(
            text(
                "SELECT id, user_id, origem, caminho_original FROM videos "
                "WHERE id = :i AND user_id = :u"
            ),
            {"i": job_id, "u": user_id},
        ).all()


def test_isolamento_upload_grava_video_do_dono(ambiente, criar_usuario, fila_simulada):
    a = criar_usuario("a@exemplo.com", "usuario_a")

    job_id = _enviar(a)

    linhas = _linhas_video(ambiente, job_id, a.id)
    assert len(linhas) == 1
    assert str(linhas[0].id) == job_id
    assert str(linhas[0].user_id) == a.id
    assert linhas[0].origem == "upload"
    assert job_id in linhas[0].caminho_original


def test_isolamento_usuario_b_recebe_404_em_status_do_job_de_a(
    ambiente, criar_usuario, fila_simulada
):
    a = criar_usuario("a@exemplo.com", "usuario_a")
    b = criar_usuario("b@exemplo.com", "usuario_b")
    job_a = _enviar(a)

    de_b = b.cliente.get(f"/api/v1/status/{job_a}")
    inexistente = b.cliente.get(f"/api/v1/status/{uuid.uuid4()}")

    assert de_b.status_code == 404
    assert inexistente.status_code == 404
    assert de_b.json() == inexistente.json()
    assert job_a not in de_b.text


def test_isolamento_usuario_b_recebe_404_em_download_do_job_de_a(
    ambiente, criar_usuario, fila_simulada
):
    a = criar_usuario("a@exemplo.com", "usuario_a")
    b = criar_usuario("b@exemplo.com", "usuario_b")
    job_a = _enviar(a)
    _gravar_srt(job_a)

    de_b = b.cliente.get(f"/api/v1/download/{job_a}")
    inexistente = b.cliente.get(f"/api/v1/download/{uuid.uuid4()}")

    assert de_b.status_code == 404
    assert inexistente.status_code == 404
    assert de_b.json() == inexistente.json()
    assert "Olá" not in de_b.text


def test_isolamento_usuario_a_continua_lendo_o_proprio_job(ambiente, criar_usuario, fila_simulada):
    a = criar_usuario("a@exemplo.com", "usuario_a")
    b = criar_usuario("b@exemplo.com", "usuario_b")
    job_a = _enviar(a)
    _gravar_srt(job_a)
    assert b.cliente.get(f"/api/v1/status/{job_a}").status_code == 404

    status = a.cliente.get(f"/api/v1/status/{job_a}")
    download = a.cliente.get(f"/api/v1/download/{job_a}")

    assert status.status_code == 200
    assert status.json()["job_id"] == job_a
    assert download.status_code == 200
    assert "Olá" in download.text


def test_isolamento_consulta_ao_banco_por_user_id_errado_nao_retorna_linha(
    ambiente, criar_usuario, fila_simulada
):
    a = criar_usuario("a@exemplo.com", "usuario_a")
    b = criar_usuario("b@exemplo.com", "usuario_b")
    job_a = _enviar(a)

    assert len(_linhas_video(ambiente, job_a, a.id)) == 1
    assert _linhas_video(ambiente, job_a, b.id) == []


def test_isolamento_arquivo_existente_sem_registro_no_banco_retorna_404(ambiente, usuario_logado):
    orfao = str(uuid.uuid4())
    _gravar_srt(orfao)

    assert usuario_logado.cliente.get(f"/api/v1/download/{orfao}").status_code == 404
    assert usuario_logado.cliente.get(f"/api/v1/status/{orfao}").status_code == 404


def test_isolamento_status_de_job_registrado_responde_so_ao_dono(
    ambiente, criar_usuario, registrar_video, monkeypatch
):
    a = criar_usuario("a@exemplo.com", "usuario_a")
    b = criar_usuario("b@exemplo.com", "usuario_b")
    job_a = str(uuid.uuid4())
    registrar_video(a.id, job_a)
    monkeypatch.setattr(
        process_video_task,
        "AsyncResult",
        lambda _id: SimpleNamespace(state="PROCESSING", info={"progress": 40, "status": "x"}),
    )

    assert a.cliente.get(f"/api/v1/status/{job_a}").status_code == 200
    assert b.cliente.get(f"/api/v1/status/{job_a}").status_code == 404


def test_isolamento_identificador_invalido_continua_400_para_logado(ambiente, usuario_logado):
    assert usuario_logado.cliente.get("/api/v1/status/nao-e-uuid").status_code == 400
    assert usuario_logado.cliente.get("/api/v1/download/a_b").status_code == 400
