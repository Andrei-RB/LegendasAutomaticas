from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.nucleo.autenticacao import ESPERA_HASH_S, Sobrecarregado


async def tratar_sobrecarga(_: Request, __: Sobrecarregado) -> JSONResponse:
    return JSONResponse(
        {"detail": "Servidor ocupado; tente novamente."},
        status_code=503,
        headers={"Retry-After": str(ESPERA_HASH_S)},
    )


async def tratar_validacao(_: Request, erro: RequestValidationError) -> JSONResponse:
    """Responde 422 sem ecoar o valor recebido, que pode ser uma senha."""
    detalhes = [
        {"loc": list(item["loc"]), "msg": item["msg"], "type": item["type"]}
        for item in erro.errors()
    ]
    return JSONResponse({"detail": detalhes}, status_code=422)
