import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.core.config import settings
from app.core.logger import logger

# Import API routers
from app.api.endpoints import router as api_router

# Import security middlewares
from app.security.middleware import setup_middlewares

app = FastAPI(
    title=settings.APP_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json" if settings.DEBUG else None, # Hide OpenAPI in prod
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# Apply OWASP/NIST secure headers and CORS
setup_middlewares(app)

# Include Backend API
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.on_event("startup")
async def startup_event():
    logger.info("Application starting up...")

# Serve Frontend static files securely at root as full static host template fallback
app.mount("/", StaticFiles(directory="frontend", html=True), name="static")
