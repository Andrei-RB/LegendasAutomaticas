from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.esquemas.auth import CadastroEntrada, LoginEntrada, UsuarioSaida
from app.modelos.usuario import Usuario
from app.nucleo.autenticacao import (
    HASH_FALSO,
    NOME_COOKIE,
    TokenInvalido,
    emitir_token,
    hash_senha,
    precisa_novo_hash,
    revogar,
    validar_token,
    verificar_senha,
)
from app.nucleo.config_auth import config_auth
from app.nucleo.dependencias import obter_redis, obter_sessao, usuario_atual
from app.nucleo.logger import logger

CHAVE_LOCK_CADASTRO = 7_150_015


router = APIRouter(prefix="/auth", tags=["auth"])


def _credenciais_invalidas() -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, "E-mail ou senha incorretos.")


def _cadastro_fechado(sessao: Session) -> bool:
    ha_usuario = sessao.scalar(select(exists().where(Usuario.id.is_not(None))))
    return bool(ha_usuario) and not config_auth.PERMITIR_CADASTRO


def _opcoes_cookie() -> dict:
    return {
        "path": "/",
        "httponly": True,
        "samesite": "strict",
        "secure": config_auth.COOKIE_SECURE,
    }


@router.post("/cadastro", response_model=UsuarioSaida, status_code=status.HTTP_201_CREATED)
def cadastro(corpo: CadastroEntrada, sessao: Annotated[Session, Depends(obter_sessao)]) -> Usuario:
    negado = HTTPException(status.HTTP_403_FORBIDDEN, "Cadastro não permitido.")
    if _cadastro_fechado(sessao):
        raise negado
    sessao.rollback()
    senha_hash = hash_senha(corpo.senha)
    # O lock serializa cadastros concorrentes: só o primeiro passa com o cadastro fechado.
    sessao.execute(select(func.pg_advisory_xact_lock(CHAVE_LOCK_CADASTRO)))
    if _cadastro_fechado(sessao):
        sessao.rollback()
        raise negado
    usuario = Usuario(email=corpo.email, nome_usuario=corpo.nome_usuario, senha_hash=senha_hash)
    sessao.add(usuario)
    try:
        sessao.commit()
    except IntegrityError:
        sessao.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "E-mail ou nome de usuário já cadastrado."
        ) from None
    logger.info(f"Usuário cadastrado: {usuario.id}")
    return usuario


@router.post("/login", response_model=UsuarioSaida)
def login(
    corpo: LoginEntrada, response: Response, sessao: Annotated[Session, Depends(obter_sessao)]
) -> Usuario:
    usuario = sessao.scalar(select(Usuario).where(Usuario.email == corpo.email))
    ativo = usuario is not None and usuario.ativo
    sessao.commit()
    # Verifica sempre um hash, para que o tempo não revele se a conta existe.
    referencia = usuario.senha_hash if usuario is not None else HASH_FALSO
    senha_confere = verificar_senha(referencia, corpo.senha)
    if usuario is None or not ativo or not senha_confere:
        logger.warning("Login recusado.")
        raise _credenciais_invalidas()
    if precisa_novo_hash(usuario.senha_hash):
        usuario.senha_hash = hash_senha(corpo.senha)
        sessao.commit()
    token, _ = emitir_token(
        usuario.id, config_auth.JWT_SECRET.get_secret_value(), config_auth.JWT_EXPIRA_MINUTOS
    )
    response.set_cookie(
        NOME_COOKIE, token, max_age=config_auth.JWT_EXPIRA_MINUTOS * 60, **_opcoes_cookie()
    )
    logger.info(f"Login: {usuario.id}")
    return usuario


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, cache: Annotated[Redis, Depends(obter_redis)]) -> Response:
    resposta = Response(status_code=status.HTTP_204_NO_CONTENT)
    resposta.delete_cookie(NOME_COOKIE, **_opcoes_cookie())
    token = request.cookies.get(NOME_COOKIE)
    if not token:
        return resposta
    try:
        dados = validar_token(token, config_auth.JWT_SECRET.get_secret_value())
    except TokenInvalido:
        return resposta
    try:
        revogar(cache, dados)
    except RedisError as erro:
        logger.error(f"Falha ao revogar a sessão: {type(erro).__name__}")
        resposta.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return resposta


@router.get("/eu", response_model=UsuarioSaida)
def eu(usuario: Annotated[Usuario, Depends(usuario_atual)]) -> Usuario:
    return usuario
