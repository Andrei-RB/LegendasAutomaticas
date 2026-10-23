import base64
import json
import time
import uuid
from http.cookies import Morsel, SimpleCookie
from typing import Any

import jwt

from app.nucleo.config_auth import config_auth as settings

NOME_COOKIE = "viraliza_sessao"
BASE_AUTH = "/api/v1/auth"


def segredo() -> str:
    return settings.JWT_SECRET.get_secret_value()


def montar_token(
    sub: Any,
    *,
    expira_em: int = 3600,
    jti: str | None = None,
    algoritmo: str = "HS256",
    chave: str | None = None,
    omitir: tuple[str, ...] = (),
) -> str:
    """Emite um JWT arbitrário (inclusive inválido) para exercitar a validação."""
    agora = int(time.time())
    carga: dict[str, Any] = {
        "sub": str(sub),
        "iat": agora - (7200 if expira_em < 0 else 0),
        "exp": agora + expira_em,
        "jti": jti or uuid.uuid4().hex,
    }
    for campo in omitir:
        carga.pop(campo)
    if algoritmo == "none":
        return jwt.encode(carga, None, algorithm="none")
    return jwt.encode(carga, chave if chave is not None else segredo(), algorithm=algoritmo)


def adulterar_carga(token: str, **mudancas: Any) -> str:
    """Altera a carga mantendo a assinatura original."""
    cabecalho, carga, assinatura = token.split(".")
    dados = json.loads(base64.urlsafe_b64decode(carga + "=" * (-len(carga) % 4)))
    dados.update(mudancas)
    nova = base64.urlsafe_b64encode(json.dumps(dados).encode()).rstrip(b"=").decode()
    return f"{cabecalho}.{nova}.{assinatura}"


def trocar_assinatura(token: str) -> str:
    cabecalho, carga, assinatura = token.split(".")
    primeiro = "A" if assinatura[0] != "A" else "B"
    return f"{cabecalho}.{carga}.{primeiro}{assinatura[1:]}"


def cabecalho_cookie(token: str) -> dict[str, str]:
    return {"Cookie": f"{NOME_COOKIE}={token}"}


def cookie_sessao(resposta: Any) -> Morsel:
    for bruto in resposta.headers.get_list("set-cookie"):
        cookie: SimpleCookie = SimpleCookie()
        cookie.load(bruto)
        if NOME_COOKIE in cookie:
            return cookie[NOME_COOKIE]
    raise AssertionError(f"Set-Cookie de {NOME_COOKIE} ausente na resposta")


def token_da_resposta(resposta: Any) -> str:
    return cookie_sessao(resposta).value


def token_do_cliente(cliente: Any) -> str:
    token = cliente.cookies.get(NOME_COOKIE)
    assert token, "cliente sem cookie de sessão"
    return token


def decodificar(token: str) -> dict[str, Any]:
    return jwt.decode(token, segredo(), algorithms=["HS256"])


def cadastrar(cliente: Any, email: str, senha: str, nome_usuario: str = "ana", **extra: Any):
    corpo = {"email": email, "senha": senha, "nome_usuario": nome_usuario, **extra}
    return cliente.post(f"{BASE_AUTH}/cadastro", json=corpo)


def entrar(cliente: Any, email: str, senha: str):
    return cliente.post(f"{BASE_AUTH}/login", json={"email": email, "senha": senha})
