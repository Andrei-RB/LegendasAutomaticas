from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy.orm import Session, sessionmaker

from app.modelos.usuario import Usuario
from app.nucleo.autenticacao import NOME_COOKIE, TokenInvalido, esta_revogado, validar_token
from app.nucleo.banco import criar_fabrica_sessao, criar_motor
from app.nucleo.config import settings
from app.nucleo.config_auth import config_auth
from app.nucleo.logger import logger

TIMEOUT_REDIS_S = 2


@lru_cache(maxsize=1)
def _fabrica() -> sessionmaker[Session]:
    return criar_fabrica_sessao(criar_motor(settings.DATABASE_URL.get_secret_value()))


@lru_cache(maxsize=1)
def _cliente_redis() -> Redis:
    return Redis.from_url(
        settings.REDIS_URL,
        socket_timeout=TIMEOUT_REDIS_S,
        socket_connect_timeout=TIMEOUT_REDIS_S,
        health_check_interval=30,
    )


def obter_sessao() -> Iterator[Session]:
    with _fabrica()() as sessao:
        yield sessao


def obter_redis() -> Redis:
    return _cliente_redis()


def nao_autenticado() -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, "Não autenticado.")


def usuario_atual(
    request: Request,
    sessao: Annotated[Session, Depends(obter_sessao)],
    cache: Annotated[Redis, Depends(obter_redis)],
) -> Usuario:
    token = request.cookies.get(NOME_COOKIE)
    if not token:
        raise nao_autenticado()
    try:
        dados = validar_token(token, config_auth.JWT_SECRET.get_secret_value())
    except TokenInvalido:
        raise nao_autenticado() from None
    try:
        revogado = esta_revogado(cache, dados.jti)
    except RedisError as erro:
        # Sem a lista de revogação não há como confiar no token: nega o acesso.
        logger.error(f"Redis indisponível ao validar a sessão: {type(erro).__name__}")
        raise nao_autenticado() from None
    if revogado:
        raise nao_autenticado()
    usuario = sessao.get(Usuario, dados.user_id)
    # Devolve a conexão ao pool; o objeto segue utilizável (expire_on_commit=False).
    sessao.commit()
    if usuario is None or not usuario.ativo:
        raise nao_autenticado()
    return usuario
