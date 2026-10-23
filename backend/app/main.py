from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.v1.analises import router as roteador_analises
from app.api.v1.auth import router as roteador_auth
from app.api.v1.endpoints import router as roteador_v1
from app.nucleo.autenticacao import Sobrecarregado
from app.nucleo.config import settings
from app.nucleo.erros import tratar_sobrecarga, tratar_validacao
from app.nucleo.logger import logger
from app.nucleo.seguranca import configurar_middlewares


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Aplicação iniciando.")
    yield
    logger.info("Aplicação encerrando.")


app = FastAPI(
    title=settings.APP_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json" if settings.DEBUG else None,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

configurar_middlewares(app)
app.add_exception_handler(RequestValidationError, tratar_validacao)
app.add_exception_handler(Sobrecarregado, tratar_sobrecarga)


@app.get("/health", include_in_schema=False)
async def health() -> JSONResponse:
    return JSONResponse({"status": "healthy"})


app.include_router(roteador_auth, prefix=settings.API_V1_STR)
app.include_router(roteador_v1, prefix=settings.API_V1_STR)
app.include_router(roteador_analises, prefix=settings.API_V1_STR)
