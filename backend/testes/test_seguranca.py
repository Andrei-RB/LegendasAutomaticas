import pytest
from fastapi import FastAPI

from app.main import app
from app.nucleo.config import settings
from app.nucleo.seguranca import configurar_middlewares, montar_origens_cors

BASE = ["http://localhost:8501", "http://127.0.0.1:8501", "http://localhost"]
MB = 1024 * 1024


def test_origens_base_sem_extras():
    assert montar_origens_cors("") == BASE


def test_origens_extras_com_trim_e_sem_vazios():
    origens = montar_origens_cors(" https://a.com , ,https://b.com,, ")
    assert origens == BASE + ["https://a.com", "https://b.com"]


def test_origens_sem_duplicar():
    origens = montar_origens_cors("http://localhost,https://a.com,https://a.com")
    assert origens == BASE + ["https://a.com"]
    assert len(origens) == len(set(origens))


def test_configurar_middlewares_e_chamavel():
    assert callable(configurar_middlewares)


def test_app_e_fastapi():
    assert isinstance(app, FastAPI)


def test_cabecalhos_de_seguranca_em_toda_resposta(cliente):
    for caminho in ("/health", "/nao-existe"):
        h = cliente.get(caminho).headers
        assert h["x-content-type-options"] == "nosniff"
        assert h["x-frame-options"] == "DENY"
        assert h["referrer-policy"]
        assert h["strict-transport-security"]
        assert h["cache-control"] == "no-store"
        csp = h["content-security-policy"]
        assert "default-src 'none'" in csp
        assert "unsafe-inline" not in csp


def test_cors_origem_nao_listada_sem_permissao(cliente):
    resposta = cliente.get("/health", headers={"Origin": "https://malicioso.example"})
    assert "access-control-allow-origin" not in resposta.headers


def test_cors_origem_listada_recebe_permissao(cliente):
    resposta = cliente.get("/health", headers={"Origin": "http://localhost:8501"})
    assert resposta.headers.get("access-control-allow-origin") == "http://localhost:8501"


def test_content_length_acima_do_limite_retorna_413(cliente, monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE", 2 * MB)
    resposta = cliente.post(
        "/api/v1/upload-video",
        content=b"x",
        headers={"Content-Length": str(3 * MB)},
    )
    assert resposta.status_code == 413
    assert "2 MB" in resposta.json()["detail"]


def test_content_length_dentro_do_limite_nao_retorna_413(cliente, monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE", 2 * MB)
    resposta = cliente.post("/api/v1/upload-video", content=b"x")
    assert resposta.status_code != 413


@pytest.mark.parametrize("valor", ["abc", "-", "1.5", "12abc"])
def test_content_length_nao_numerico_retorna_400(cliente, valor):
    resposta = cliente.post("/api/v1/upload-video", content=b"x", headers={"Content-Length": valor})
    assert resposta.status_code == 400
    assert "detail" in resposta.json()


def test_resposta_413_tambem_traz_cabecalhos_de_seguranca(cliente, monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE", 2 * MB)
    resposta = cliente.post(
        "/api/v1/upload-video", content=b"x", headers={"Content-Length": str(3 * MB)}
    )
    assert resposta.headers["x-content-type-options"] == "nosniff"
