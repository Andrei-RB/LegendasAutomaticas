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
def test_status_cobre_os_estados_da_tarefa(cliente, monkeypatch, estado, info, esperado):
    monkeypatch.setattr(process_video_task, "AsyncResult", _resultado(estado, info))
    resposta = cliente.get(f"/api/v1/status/{uuid.uuid4()}")
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert {chave: corpo[chave] for chave in esperado} == esperado


def test_download_devolve_o_srt_existente(cliente):
    job_id = str(uuid.uuid4())
    caminho = os.path.join(settings.OUTPUT_DIR, f"{job_id}.srt")
    with open(caminho, "w", encoding="utf-8") as arquivo:
        arquivo.write("1\n00:00:00,000 --> 00:00:01,000\nOlá\n\n")

    resposta = cliente.get(f"/api/v1/download/{job_id}")

    assert resposta.status_code == 200
    assert "Olá" in resposta.text
    assert f"legenda_{job_id}.srt" in resposta.headers["content-disposition"]


@pytest.fixture
def temporarios(monkeypatch):
    base = Path(settings.UPLOAD_DIR)
    video = base / f"{uuid.uuid4()}.mp4"
    audio = base / f"{uuid.uuid4()}.wav"
    video.write_bytes(b"v")
    audio.write_bytes(b"a")
    monkeypatch.setattr(process_video_task, "update_state", lambda **_: None)
    monkeypatch.setattr(tasks, "extrair_audio", lambda *_: str(audio))
    return video, audio


def test_tarefa_remove_temporarios_no_sucesso(temporarios, monkeypatch):
    video, audio = temporarios
    monkeypatch.setattr(tasks, "transcrever_e_gerar_srt", lambda *_: "saida.srt")

    resultado = process_video_task.run(str(video), "job-1")

    assert resultado["result_url"] == "/api/v1/download/job-1"
    assert not video.exists()
    assert not audio.exists()


def test_tarefa_remove_temporarios_na_falha(temporarios, monkeypatch):
    video, audio = temporarios

    def falhar(*_):
        raise RuntimeError("modelo indisponível")

    monkeypatch.setattr(tasks, "transcrever_e_gerar_srt", falhar)

    with pytest.raises(Ignore):
        process_video_task.run(str(video), "job-2")

    assert not video.exists()
    assert not audio.exists()


def test_tarefa_recusa_caminho_fora_do_upload_sem_apagar(tmp_path, monkeypatch):
    alheio = tmp_path / "alheio.mp4"
    alheio.write_bytes(b"v")
    estados = []
    monkeypatch.setattr(process_video_task, "update_state", lambda **k: estados.append(k))

    with pytest.raises(Ignore):
        process_video_task.run(str(alheio), "job-3")

    assert alheio.exists()
    assert estados[-1]["state"] == "FAILURE"


def test_tarefa_falha_publica_somente_mensagem_fixa(temporarios, monkeypatch):
    video, _ = temporarios
    estados = []
    monkeypatch.setattr(process_video_task, "update_state", lambda **k: estados.append(k))

    def falhar(*_):
        raise RuntimeError("segredo em /var/interno/arquivo")

    monkeypatch.setattr(tasks, "transcrever_e_gerar_srt", falhar)

    with pytest.raises(Ignore):
        process_video_task.run(str(video), "job-4")

    assert "segredo" not in str(estados[-1])
    assert estados[-1]["meta"]["status"] == MENSAGEM_FALHA


def test_meta_de_falha_e_legivel_pelo_celery():
    aplicacao = Celery("t", backend="cache+memory://", broker="memory://")
    aplicacao.backend.store_result("falha", meta_falha(MENSAGEM_FALHA), "FAILURE")

    resultado = aplicacao.AsyncResult("falha")

    assert resultado.state == "FAILURE"
    assert MENSAGEM_FALHA in str(resultado.info)


def test_status_de_falha_nao_expoe_detalhe_interno(cliente, monkeypatch):
    info = RuntimeError("erro em C:/interno/segredo.mp4")
    monkeypatch.setattr(process_video_task, "AsyncResult", _resultado("FAILURE", info))

    corpo = cliente.get(f"/api/v1/status/{uuid.uuid4()}").json()

    assert corpo["error"] == MENSAGEM_FALHA
    assert "segredo" not in str(corpo)


def test_status_com_identificador_invalido_retorna_400(cliente):
    assert cliente.get("/api/v1/status/nao-e-um-uuid").status_code == 400
