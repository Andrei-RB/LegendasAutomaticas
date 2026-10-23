import threading

import pytest

from testes.auxiliares_auth import BASE_AUTH, cabecalho_cookie, montar_token, trocar_assinatura

CABECALHO_MULTIPART = {"Content-Type": "multipart/form-data; boundary=x"}


def _corpo_grande():
    yield b'--x\r\nContent-Disposition: form-data; name="file"; filename="v.mp4"\r\n\r\n'
    for _ in range(4):
        yield b"0" * (512 * 1024)


def test_upload_anonimo_e_recusado_antes_de_ler_o_corpo(ambiente, novo_cliente):
    resposta = novo_cliente().post(
        "/api/v1/upload-video", content=_corpo_grande(), headers=CABECALHO_MULTIPART
    )

    assert resposta.status_code == 401


def test_upload_com_token_de_assinatura_invalida_e_recusado_antes_de_ler_o_corpo(
    ambiente, novo_cliente
):
    token = trocar_assinatura(montar_token("00000000-0000-4000-8000-000000000000"))

    resposta = novo_cliente().post(
        "/api/v1/upload-video",
        content=_corpo_grande(),
        headers={**CABECALHO_MULTIPART, **cabecalho_cookie(token)},
    )

    assert resposta.status_code == 401


@pytest.mark.parametrize("caminho", ["login", "cadastro"])
def test_corpo_json_acima_de_16_kib_retorna_413(ambiente, novo_cliente, caminho):
    corpo = b'{"email": "' + b"a" * (17 * 1024) + b'"}'

    resposta = novo_cliente().post(
        f"{BASE_AUTH}/{caminho}", content=corpo, headers={"Content-Type": "application/json"}
    )

    assert resposta.status_code == 413


def test_corpo_json_chunked_acima_de_16_kib_retorna_413(ambiente, novo_cliente):
    def corpo():
        yield b'{"email": "'
        for _ in range(17):
            yield b"a" * 1024

    resposta = novo_cliente().post(
        f"{BASE_AUTH}/login", content=corpo(), headers={"Content-Type": "application/json"}
    )

    assert resposta.status_code == 413


def test_login_sem_vaga_para_hash_retorna_503_com_retry_after(
    ambiente, usuario_logado, novo_cliente, monkeypatch
):
    from app.nucleo import autenticacao

    monkeypatch.setattr(autenticacao, "_LIMITE_HASH", threading.BoundedSemaphore(1))
    monkeypatch.setattr(autenticacao, "ESPERA_HASH_S", 0.05)
    autenticacao._LIMITE_HASH.acquire()

    resposta = novo_cliente().post(
        f"{BASE_AUTH}/login", json={"email": usuario_logado.email, "senha": usuario_logado.senha}
    )

    assert resposta.status_code == 503
    assert "retry-after" in resposta.headers


@pytest.mark.parametrize("email_login", ["JOSÉ@EXEMPLO.COM", " josé@exemplo.com "])
def test_login_normaliza_o_email_como_o_cadastro(criar_usuario, novo_cliente, email_login):
    usuario = criar_usuario(email="josé@exemplo.com", nome_usuario="jose")

    resposta = novo_cliente().post(
        f"{BASE_AUTH}/login", json={"email": email_login, "senha": usuario.senha}
    )

    assert resposta.status_code == 200


def test_middleware_de_upload_recusa_sem_consumir_o_corpo():
    import asyncio

    from app.nucleo.seguranca import MiddlewareSessaoNoUpload

    chamadas = []

    async def interno(scope, receive, send):
        chamadas.append("interno")

    async def receive():
        raise AssertionError("o corpo não deve ser lido")

    enviadas = []

    async def send(mensagem):
        enviadas.append(mensagem)

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/upload-video",
        "headers": [],
    }
    asyncio.run(MiddlewareSessaoNoUpload(interno)(scope, receive, send))

    assert chamadas == []
    assert enviadas[0]["status"] == 401
