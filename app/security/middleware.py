from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from app.core.logger import logger
from app.core.config import settings

class MiddlewareCabecalhosSeguranca(BaseHTTPMiddleware):
    async def dispatch(self, requisicao: Request, proximo):
        # Não logar requests de healthcheck para evitar poluição de logs
        if requisicao.url.path == "/health":
            return await proximo(requisicao)

        logger.info(f"-> Requisição: {requisicao.method} {requisicao.url.path}")
        resposta = await proximo(requisicao)
        
        # APLICAÇÃO DE POLÍTICAS ESTRITAS DE CABEÇALHOS (OWASP/NIST)
        resposta.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'"
        resposta.headers["X-Frame-Options"] = "DENY"
        resposta.headers["X-Content-Type-Options"] = "nosniff"
        resposta.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        resposta.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        resposta.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        logger.info(f"<- Resposta: {requisicao.method} {requisicao.url.path} - {resposta.status_code}")
        return resposta

class MiddlewareLimiteCargaUtil(BaseHTTPMiddleware):
    async def dispatch(self, requisicao: Request, proximo):
        # MITIGAÇÃO DE DOS: Bloqueio imediato na borda baseado no cabeçalho
        tamanho_conteudo = requisicao.headers.get("content-length")
        if tamanho_conteudo and int(tamanho_conteudo) > settings.MAX_UPLOAD_SIZE:
            return Response("Carga útil recusa por exceder limite estrutural seguro.", status_code=413)
        return await proximo(requisicao)

def setup_middlewares(aplicativo: FastAPI):
    # MITIGAÇÃO CORS: Lista branca configurável com fallback seguro
    origens_permitidas = [
        "http://localhost:8501",
        "http://127.0.0.1:8501",
        "http://localhost",
    ]

    # Adicionar origens de produção configuradas via variável de ambiente
    if settings.CORS_ORIGINS:
        origens_extras = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
        origens_permitidas.extend(origens_extras)

    aplicativo.add_middleware(
        CORSMiddleware,
        allow_origins=origens_permitidas,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    
    aplicativo.add_middleware(MiddlewareLimiteCargaUtil)
    aplicativo.add_middleware(MiddlewareCabecalhosSeguranca)
