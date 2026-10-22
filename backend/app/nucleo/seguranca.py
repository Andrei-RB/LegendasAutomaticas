from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.nucleo.config import settings
from app.nucleo.logger import logger
from app.nucleo.validacao import mensagem_limite_upload

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
    async def dispatch(self, requisicao: Request, proximo):
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


class MiddlewareLimiteCargaUtil(BaseHTTPMiddleware):
    async def dispatch(self, requisicao: Request, proximo):
        declarado = requisicao.headers.get("content-length")
        if declarado is not None:
            if not declarado.isascii() or not declarado.isdigit():
                return JSONResponse({"detail": "Content-Length inválido."}, status_code=400)
            if int(declarado) > settings.MAX_UPLOAD_SIZE:
                return JSONResponse({"detail": mensagem_limite_upload()}, status_code=413)
        return await proximo(requisicao)


def montar_origens_cors(extras: str) -> list[str]:
    origens = list(ORIGENS_BASE)
    for origem in (o.strip() for o in extras.split(",")):
        if origem and origem not in origens:
            origens.append(origem)
    return origens


def configurar_middlewares(aplicativo: FastAPI) -> None:
    # O último adicionado é o mais externo: o CORS envolve também as respostas de recusa.
    aplicativo.add_middleware(MiddlewareLimiteCargaUtil)
    aplicativo.add_middleware(MiddlewareCabecalhosSeguranca)
    aplicativo.add_middleware(
        CORSMiddleware,
        allow_origins=montar_origens_cors(settings.CORS_ORIGINS),
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
