from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from app.core.logger import logger

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        logger.info(f"-> Requisição: {request.method} {request.url.path}")
        response = await call_next(request)
        # Apply OWASP/NIST Secure Headers
        response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        logger.info(f"<- Resposta: {request.method} {request.url.path} - {response.status_code}")
        return response

def setup_middlewares(app: FastAPI):
    # CORS setup: Note, restricts to development access initially, but allows all here for simplicity.
    # In strict NIST envs, specify origins.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Adjust this in production! e.g., ["http://localhost:8000"]
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    # Apply security headers
    app.add_middleware(SecurityHeadersMiddleware)
