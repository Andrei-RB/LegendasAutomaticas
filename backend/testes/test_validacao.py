import asyncio
import io
import uuid

import pytest
from fastapi import HTTPException, UploadFile

from app.nucleo.config import settings
from app.nucleo.validacao import job_id_valido, mensagem_limite_upload, validar_arquivo_video

MB = 1024 * 1024


def _arquivo(nome: str, tamanho: int) -> UploadFile:
    return UploadFile(file=io.BytesIO(b"\0" * tamanho), filename=nome)


def test_mensagem_limite_le_configuracao_a_cada_chamada(monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE", 2 * MB)
    assert mensagem_limite_upload() == "Arquivo muito grande. Limite é de 2 MB."
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE", 5 * MB)
    assert mensagem_limite_upload() == "Arquivo muito grande. Limite é de 5 MB."


def test_arquivo_acima_do_limite_retorna_413(monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE", 2 * MB)
    with pytest.raises(HTTPException) as erro:
        asyncio.run(validar_arquivo_video(_arquivo("video.mp4", 3 * MB)))
    assert erro.value.status_code == 413
    assert "2 MB" in erro.value.detail


def test_extensao_invalida_retorna_400():
    with pytest.raises(HTTPException) as erro:
        asyncio.run(validar_arquivo_video(_arquivo("script.js", 10)))
    assert erro.value.status_code == 400
    assert "permitida" in erro.value.detail.lower()


def test_arquivo_valido_retorna_true(monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE", 2 * MB)
    assert asyncio.run(validar_arquivo_video(_arquivo("video.mp4", 1024))) is True


def test_arquivo_exatamente_no_limite_e_aceito(monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE", 2 * MB)
    assert asyncio.run(validar_arquivo_video(_arquivo("video.mp4", 2 * MB))) is True


def test_arquivo_vazio_e_aceito_pela_validacao(monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE", 2 * MB)
    assert asyncio.run(validar_arquivo_video(_arquivo("video.mp4", 0))) is True


def test_extensao_dupla_maliciosa_rejeitada():
    with pytest.raises(HTTPException) as erro:
        asyncio.run(validar_arquivo_video(_arquivo("video.mp4.exe", 10)))
    assert erro.value.status_code == 400


def test_nome_com_path_traversal_rejeitado():
    with pytest.raises(HTTPException) as erro:
        asyncio.run(validar_arquivo_video(_arquivo("../../etc/passwd", 10)))
    assert erro.value.status_code == 400


def test_nome_unicode_com_extensao_valida_aceito(monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE", 2 * MB)
    assert asyncio.run(validar_arquivo_video(_arquivo("vídeo_ação_日本.mp4", 10))) is True


def test_extensao_em_maiusculas_aceita(monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE", 2 * MB)
    assert asyncio.run(validar_arquivo_video(_arquivo("VIDEO.MP4", 10))) is True


@pytest.mark.parametrize(
    ("job_id", "esperado"),
    [
        (str(uuid.uuid4()), True),
        ("12345678123456781234567812345678", False),
        ("{12345678-1234-5678-1234-567812345678}", False),
        ("ABCDEF12-1234-5678-1234-567812345678", False),
        ("../../x", False),
        ("", False),
    ],
)
def test_job_id_valido_aceita_so_uuid_canonico(job_id, esperado):
    assert job_id_valido(job_id) is esperado
