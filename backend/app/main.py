from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.v1.endpoints import router as roteador_v1
from app.nucleo.config import settings
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


@app.get("/health", include_in_schema=False)
async def health() -> JSONResponse:
    return JSONResponse({"status": "healthy"})


app.include_router(roteador_v1, prefix=settings.API_V1_STR)
