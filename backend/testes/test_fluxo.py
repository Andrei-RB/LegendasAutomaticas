import os
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from celery import Celery
from celery.exceptions import Ignore

from app.nucleo.config import settings
from app.workers import tasks
from app.workers.tasks import MENSAGEM_FALHA, meta_falha, process_video_task


def _resultado(estado, info=None):
    return lambda _job_id: SimpleNamespace(state=estado, info=info)


@pytest.mark.parametrize(
    ("estado", "info", "esperado"),
    [
        ("PENDING", None, {"status": "PENDING", "progress": 0}),
        ("FAILURE", RuntimeError("falhou"), {"status": "FAILURE", "error": MENSAGEM_FALHA}),
        (
            "PROCESSING",
            {"status": "Transcrevendo", "progress": 42},
            {"status": "Transcrevendo", "progress": 42},
        ),
        (
            "SUCCESS",
            {"progress": 100, "result_url": "/api/v1/download/x"},
            {"progress": 100, "result_url": "/api/v1/download/x"},
        ),
        ("STARTED", None, {"status": "STARTED", "progress": 0}),
    ],
)
def test_status_cobre_os_estados_da_tarefa(
    usuario_logado, registrar_video, monkeypatch, estado, info, esperado
):
    monkeypatch.setattr(process_video_task, "AsyncResult", _resultado(estado, info))
    job_id = str(uuid.uuid4())
    registrar_video(usuario_logado.id, job_id)
    resposta = usuario_logado.cliente.get(f"/api/v1/status/{job_id}")
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert {chave: corpo[chave] for chave in esperado} == esperado


def test_download_devolve_o_srt_existente(usuario_logado, registrar_video):
    job_id = str(uuid.uuid4())
    registrar_video(usuario_logado.id, job_id)
    caminho = os.path.join(settings.OUTPUT_DIR, f"{job_id}.srt")
    with open(caminho, "w", encoding="utf-8") as arquivo:
        arquivo.write("1\n00:00:00,000 --> 00:00:01,000\nOlá\n\n")

    resposta = usuario_logado.cliente.get(f"/api/v1/download/{job_id}")

    assert resposta.status_code == 200
    assert "Olá" in resposta.text
    assert f"legenda_{job_id}.srt" in resposta.headers["content-disposition"]


@pytest.fixture
def temporarios(monkeypatch):
    base = Path(settings.UPLOAD_DIR)
    job_id = str(uuid.uuid4())
    video = base / f"{job_id}.mp4"
    audio = base / f"{job_id}.wav"
    video.write_bytes(b"v")
    audio.write_bytes(b"a")
    monkeypatch.setattr(process_video_task, "update_state", lambda **_: None)
    monkeypatch.setattr(tasks, "extrair_audio", lambda *_: str(audio))
    return video, audio, job_id


def test_tarefa_remove_temporarios_no_sucesso(temporarios, monkeypatch):
    video, audio, job_id = temporarios
    monkeypatch.setattr(tasks, "transcrever_e_gerar_srt", lambda *_: "saida.srt")

    resultado = process_video_task.run(str(video), job_id)

    assert resultado["result_url"] == f"/api/v1/download/{job_id}"
    assert not video.exists()
    assert not audio.exists()


def test_tarefa_remove_temporarios_na_falha(temporarios, monkeypatch):
    video, audio, job_id = temporarios

    def falhar(*_):
        raise RuntimeError("modelo indisponível")

    monkeypatch.setattr(tasks, "transcrever_e_gerar_srt", falhar)

    with pytest.raises(Ignore):
        process_video_task.run(str(video), job_id)

    assert not video.exists()
    assert not audio.exists()


def test_tarefa_recusa_caminho_fora_do_upload_sem_apagar(tmp_path, monkeypatch):
    job_id = str(uuid.uuid4())
    alheio = tmp_path / f"{job_id}.mp4"
    alheio.write_bytes(b"v")
    estados = []
    monkeypatch.setattr(process_video_task, "update_state", lambda **k: estados.append(k))

    with pytest.raises(Ignore):
        process_video_task.run(str(alheio), job_id)

    assert alheio.exists()
    assert estados[-1]["state"] == "FAILURE"


def test_tarefa_falha_publica_somente_mensagem_fixa(temporarios, monkeypatch):
    video, _, job_id = temporarios
    estados = []
    monkeypatch.setattr(process_video_task, "update_state", lambda **k: estados.append(k))

    def falhar(*_):
        raise RuntimeError("segredo em /var/interno/arquivo")

    monkeypatch.setattr(tasks, "transcrever_e_gerar_srt", falhar)

    with pytest.raises(Ignore):
        process_video_task.run(str(video), job_id)

    assert "segredo" not in str(estados[-1])
    assert estados[-1]["meta"]["status"] == MENSAGEM_FALHA


def test_meta_de_falha_e_legivel_pelo_celery():
    aplicacao = Celery("t", backend="cache+memory://", broker="memory://")
    aplicacao.backend.store_result("falha", meta_falha(MENSAGEM_FALHA), "FAILURE")

    resultado = aplicacao.AsyncResult("falha")

    assert resultado.state == "FAILURE"
    assert MENSAGEM_FALHA in str(resultado.info)


def test_status_de_falha_nao_expoe_detalhe_interno(usuario_logado, registrar_video, monkeypatch):
    info = RuntimeError("erro em C:/interno/segredo.mp4")
    monkeypatch.setattr(process_video_task, "AsyncResult", _resultado("FAILURE", info))
    job_id = str(uuid.uuid4())
    registrar_video(usuario_logado.id, job_id)

    corpo = usuario_logado.cliente.get(f"/api/v1/status/{job_id}").json()

    assert corpo["error"] == MENSAGEM_FALHA
    assert "segredo" not in str(corpo)


def test_status_com_identificador_invalido_retorna_400(cliente_logado):
    assert cliente_logado.get("/api/v1/status/nao-e-um-uuid").status_code == 400


def test_tarefa_recusa_arquivo_de_outro_job_e_job_id_invalido(monkeypatch):
    alheio = Path(settings.UPLOAD_DIR) / f"{uuid.uuid4()}.mp4"
    alheio.write_bytes(b"v")
    monkeypatch.setattr(process_video_task, "update_state", lambda **_: None)

    for job_id in (str(uuid.uuid4()), "../../x"):
        with pytest.raises(Ignore):
            process_video_task.run(str(alheio), job_id)

    assert alheio.exists()
    alheio.unlink()
