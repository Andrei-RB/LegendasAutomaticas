import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.logger import logger

# Import API routers
from app.api.endpoints import router as api_router

# Import security middlewares
from app.security.middleware import setup_middlewares

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application starting up...")
    yield
    logger.info("Application shutting down...")

app = FastAPI(
    title=settings.APP_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json" if settings.DEBUG else None, # Hide OpenAPI in prod
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# Apply OWASP/NIST secure headers and CORS
setup_middlewares(app)

# Endpoint de saúde para healthchecks do Docker e monitoramento SaaS
@app.get("/health", include_in_schema=False)
async def health_check():
    return JSONResponse(content={"status": "healthy"}, status_code=200)

# Include Backend API
app.include_router(api_router, prefix=settings.API_V1_STR)

# Serve Frontend static files securely at root as full static host template fallback
app.mount("/", StaticFiles(directory="frontend", html=True), name="static")
