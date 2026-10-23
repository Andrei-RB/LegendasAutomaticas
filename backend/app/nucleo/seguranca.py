from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.datastructures import Headers
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.nucleo.autenticacao import NOME_COOKIE, TokenInvalido, validar_token
from app.nucleo.config import settings
from app.nucleo.config_auth import config_auth
from app.nucleo.logger import logger
from app.nucleo.validacao import mensagem_limite_upload

CAMINHO_UPLOAD = "/upload-video"
LIMITE_CORPO_JSON = 16 * 1024
MENSAGEM_CORPO_JSON = "Corpo da requisição acima do limite."
AMBIENTES_LOCAIS = {"development", "dev", "local"}
ORIGENS_BASE = ["http://localhost:8501", "http://127.0.0.1:8501", "http://localhost"]

# API sem conteúdo ativo: nenhuma origem de script, estilo ou quadro é aceita.
CABECALHOS_SEGURANCA = {
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Cache-Control": "no-store",
}


class MiddlewareCabecalhosSeguranca(BaseHTTPMiddleware):
    async def dispatch(self, requisicao: Request, proximo: RequestResponseEndpoint) -> Response:
        if requisicao.url.path == "/health":
            resposta = await proximo(requisicao)
        else:
            logger.info(f"-> {requisicao.method} {requisicao.url.path}")
            resposta = await proximo(requisicao)
            logger.info(f"<- {requisicao.method} {requisicao.url.path} {resposta.status_code}")

        for nome, valor in CABECALHOS_SEGURANCA.items():
            # A interface /docs (só com DEBUG) carrega scripts externos e exige CSP mais frouxa.
            if settings.DEBUG and nome == "Content-Security-Policy":
                continue
            resposta.headers[nome] = valor
        return resposta


class MiddlewareLimiteCargaUtil:
    """Recusa corpos acima do limite, por Content-Length e pela contagem dos bytes recebidos."""

    def __init__(self, aplicativo: ASGIApp) -> None:
        self.aplicativo = aplicativo

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.aplicativo(scope, receive, send)
            return

        upload = scope["path"].endswith(CAMINHO_UPLOAD)
        limite = settings.MAX_UPLOAD_SIZE if upload else LIMITE_CORPO_JSON
        mensagem_limite = mensagem_limite_upload() if upload else MENSAGEM_CORPO_JSON
        declarado = Headers(scope=scope).get("content-length")
        if declarado is not None:
            if not (declarado.isascii() and declarado.isdigit()):
                await JSONResponse({"detail": "Content-Length inválido."}, status_code=400)(
                    scope, receive, send
                )
                return
            if int(declarado) > limite:
                await JSONResponse({"detail": mensagem_limite}, status_code=413)(
                    scope, receive, send
                )
                return

        recebidos = 0
        excedido = False
        resposta_enviada = False

        async def recusar() -> None:
            await JSONResponse({"detail": mensagem_limite}, status_code=413)(scope, receive, send)

        # Ao estourar o limite o corpo é cortado como desconexão e a resposta do app é trocada
        # por 413; o FastAPI converteria qualquer exceção de leitura em 400.
        async def receive_limitado() -> Message:
            nonlocal recebidos, excedido
            if excedido:
                return {"type": "http.disconnect"}
            mensagem = await receive()
            if mensagem["type"] == "http.request":
                recebidos += len(mensagem.get("body", b""))
                if recebidos > limite:
                    excedido = True
                    logger.warning(f"Corpo acima do limite ({limite} bytes) recusado.")
                    return {"type": "http.disconnect"}
            return mensagem

        async def send_rastreado(mensagem: Message) -> None:
            nonlocal resposta_enviada
            if excedido:
                if not resposta_enviada:
                    resposta_enviada = True
                    await recusar()
                elif mensagem["type"] == "http.response.body" and not mensagem.get("more_body"):
                    await send(mensagem)
                return
            if mensagem["type"] == "http.response.start":
                resposta_enviada = True
            await send(mensagem)

        try:
            await self.aplicativo(scope, receive_limitado, send_rastreado)
        except Exception:
            if not excedido:
                raise
        if excedido and not resposta_enviada:
            await recusar()


METODOS_QUE_ALTERAM = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class MiddlewareSessaoNoUpload:
    """Exige token válido antes de ler o corpo do upload, para não gravar dados de anônimos."""

    def __init__(self, aplicativo: ASGIApp) -> None:
        self.aplicativo = aplicativo

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] == "http"
            and scope["method"] == "POST"
            and scope["path"].endswith(CAMINHO_UPLOAD)
        ):
            token = Request(scope).cookies.get(NOME_COOKIE)
            try:
                if not token:
                    raise TokenInvalido
                validar_token(token, config_auth.JWT_SECRET.get_secret_value())
            except TokenInvalido:
                resposta = JSONResponse({"detail": "Não autenticado."}, status_code=401)
                await resposta(scope, receive, send)
                return
        await self.aplicativo(scope, receive, send)


class MiddlewareOrigemPermitida:
    """Recusa método que altera estado sem Origin permitido ou Sec-Fetch-Site same-origin."""

    def __init__(self, aplicativo: ASGIApp, origens: list[str]) -> None:
        self.aplicativo = aplicativo
        self.origens = frozenset(origens)

    def _permitida(self, cabecalhos: Headers) -> bool:
        origem = cabecalhos.get("origin")
        if origem is not None:
            return origem in self.origens
        return cabecalhos.get("sec-fetch-site") == "same-origin"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["method"] in METODOS_QUE_ALTERAM:
            if not self._permitida(Headers(scope=scope)):
                logger.warning(f"Origem recusada: {scope['method']} {scope['path']}")
                resposta = JSONResponse({"detail": "Origem não permitida."}, status_code=403)
                await resposta(scope, receive, send)
                return
        await self.aplicativo(scope, receive, send)


def _origem_valida(origem: str) -> str | None:
    partes = urlsplit(origem)
    if partes.scheme not in ("http", "https") or not partes.hostname:
        return None
    if partes.path not in ("", "/") or partes.query or partes.fragment or "*" in origem:
        return None
    return f"{partes.scheme}://{partes.netloc}"


def montar_origens_cors(extras: str, incluir_base: bool = False) -> list[str]:
    """Combina a lista local (opcional) com as origens extras válidas; descarta curingas."""
    origens = list(ORIGENS_BASE) if incluir_base else []
    for bruta in (o.strip() for o in extras.split(",")):
        if not bruta:
            continue
        origem = _origem_valida(bruta)
        if origem is None:
            logger.warning(f"Origem CORS descartada por formato inválido: {bruta!r}")
        elif origem not in origens:
            origens.append(origem)
    return origens


def configurar_middlewares(aplicativo: FastAPI) -> None:
    origens = montar_origens_cors(
        settings.CORS_ORIGINS, incluir_base=settings.APP_ENV.strip().lower() in AMBIENTES_LOCAIS
    )
    # O último adicionado é o mais externo: o CORS envolve também as respostas de recusa.
    aplicativo.add_middleware(MiddlewareSessaoNoUpload)
    aplicativo.add_middleware(MiddlewareOrigemPermitida, origens=origens)
    aplicativo.add_middleware(MiddlewareLimiteCargaUtil)
    aplicativo.add_middleware(MiddlewareCabecalhosSeguranca)
    aplicativo.add_middleware(
        CORSMiddleware,
        allow_origins=origens,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
