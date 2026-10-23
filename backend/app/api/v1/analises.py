import json
import time
import uuid
from collections import Counter
from collections.abc import AsyncIterator, Callable
from typing import Annotated, Any

import anyio
import redis.asyncio
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from redis.asyncio.client import PubSub
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from starlette.background import BackgroundTask

from app.modelos.analise import Analise, ExecucaoEtapa
from app.modelos.usuario import Usuario
from app.nucleo.autenticacao import (
    NOME_COOKIE,
    SessaoToken,
    TokenInvalido,
    chave_revogacao,
    validar_token,
)
from app.nucleo.config import settings
from app.nucleo.config_auth import config_auth
from app.nucleo.dependencias import (
    obter_fabrica_redis_assincrono,
    obter_fabrica_sessao,
    obter_sessao,
    usuario_atual,
)
from app.nucleo.logger import logger
from app.pipeline.eventos import EventoAnalise, canal

router = APIRouter()

ESTADOS_FINAIS = frozenset({"concluida", "falhou"})
ESPERA_NOVA_TENTATIVA_S = 5
TIMEOUT_REDIS_S = 5
MAX_EVENTO_BYTES = 4096
CABECALHOS_SSE = {"Cache-Control": "no-store", "X-Accel-Buffering": "no"}

# Contadores do processo: a API roda com um único processo uvicorn.
_por_usuario: Counter[uuid.UUID] = Counter()


def conexoes_ativas() -> int:
    return sum(_por_usuario.values())


class _Vaga:
    """Reserva de uma conexão SSE; a liberação é idempotente."""

    def __init__(self, user_id: uuid.UUID) -> None:
        self._user_id = user_id
        self._ativa = True

    def liberar(self) -> None:
        if not self._ativa:
            return
        self._ativa = False
        _por_usuario[self._user_id] -= 1
        if _por_usuario[self._user_id] <= 0:
            del _por_usuario[self._user_id]


def _reservar(user_id: uuid.UUID) -> _Vaga:
    if (
        _por_usuario[user_id] >= settings.SSE_MAX_POR_USUARIO
        or conexoes_ativas() >= settings.SSE_MAX_GLOBAL
    ):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Muitas conexões de acompanhamento abertas.",
            headers={"Retry-After": str(ESPERA_NOVA_TENTATIVA_S)},
        )
    _por_usuario[user_id] += 1
    return _Vaga(user_id)


def _ler_estado(
    sessao: Session, analise_id: uuid.UUID, user_id: uuid.UUID
) -> dict[str, Any] | None:
    analise = sessao.scalar(
        select(Analise).where(Analise.id == analise_id, Analise.user_id == user_id)
    )
    if analise is None:
        sessao.commit()
        return None
    ultimas = sessao.execute(
        select(ExecucaoEtapa.etapa, ExecucaoEtapa.status)
        .ext(distinct_on(ExecucaoEtapa.etapa))
        .where(ExecucaoEtapa.analise_id == analise_id, ExecucaoEtapa.user_id == user_id)
        .order_by(ExecucaoEtapa.etapa, ExecucaoEtapa.criado_em.desc())
    ).all()
    estado = {
        "analise_id": str(analise.id),
        "status": analise.status,
        "etapa_atual": analise.etapa_atual,
        "progresso": analise.progresso,
        "erro": analise.erro_amigavel,
        "etapas": [{"etapa": linha.etapa, "status": linha.status} for linha in ultimas],
    }
    # Devolve a conexão ao pool antes de manter o fluxo aberto.
    sessao.commit()
    return estado


def _quadro(evento: str, dados: str) -> str:
    return f"event: {evento}\ndata: {dados}\n\n"


def _usuario_ativo(fabrica: sessionmaker[Session], user_id: uuid.UUID) -> bool:
    with fabrica() as sessao:
        ativo = sessao.scalar(select(Usuario.ativo).where(Usuario.id == user_id))
        sessao.commit()
    return bool(ativo)


async def _sessao_vigente(
    cliente: redis.asyncio.Redis, token: SessaoToken, fabrica: sessionmaker[Session]
) -> bool:
    if token.expira_em <= time.time():
        return False
    try:
        with anyio.fail_after(TIMEOUT_REDIS_S):
            if await cliente.exists(chave_revogacao(token.jti)):
                return False
        return await run_in_threadpool(_usuario_ativo, fabrica, token.user_id)
    except (RedisError, TimeoutError, SQLAlchemyError):
        # Sem a lista de revogação ou o cadastro não há como confiar no token.
        return False


def _evento_valido(bruto: Any, analise_id: uuid.UUID) -> EventoAnalise | None:
    if len(bruto) > MAX_EVENTO_BYTES:
        logger.warning("Evento grande demais descartado no canal de progresso.")
        return None
    try:
        evento = EventoAnalise.model_validate_json(bruto)
    except (ValidationError, ValueError):
        logger.warning("Evento inválido descartado no canal de progresso.")
        return None
    if evento.analise_id != analise_id:
        logger.warning("Evento de outra análise descartado no canal de progresso.")
        return None
    return evento


async def _fluxo(
    pubsub: PubSub,
    cliente: redis.asyncio.Redis,
    estado: dict[str, Any],
    analise_id: uuid.UUID,
    token: SessaoToken,
    fabrica: sessionmaker[Session],
    vaga: _Vaga,
) -> AsyncIterator[str]:
    try:
        yield _quadro("estado", json.dumps(estado))
        if estado["status"] in ESTADOS_FINAIS:
            return
        inicio = ultimo_envio = ultima_validacao = time.monotonic()
        while True:
            intervalo = settings.SSE_HEARTBEAT_S
            agora = time.monotonic()
            restante = settings.SSE_DURACAO_MAX_S - (agora - inicio)
            if restante <= 0:
                return
            vencimento = min(ultimo_envio, ultima_validacao) + intervalo
            mensagem = await pubsub.get_message(
                ignore_subscribe_messages=True, timeout=max(0.0, min(vencimento - agora, restante))
            )
            agora = time.monotonic()
            if agora - ultima_validacao >= intervalo:
                if not await _sessao_vigente(cliente, token, fabrica):
                    return
                ultima_validacao = agora
            if mensagem is None:
                if agora - ultimo_envio >= intervalo:
                    ultimo_envio = agora
                    yield ": ping\n\n"
                continue
            evento = _evento_valido(mensagem["data"], analise_id)
            if evento is not None:
                ultimo_envio = agora
                yield _quadro(evento.tipo, evento.to_json())
                if evento.tipo == "erro":
                    return
    except RedisError as erro:
        logger.warning(f"Fluxo de progresso encerrado por falha no Redis: {type(erro).__name__}")
    finally:
        await _encerrar(pubsub, cliente, vaga)


async def _encerrar(
    pubsub: PubSub | None, cliente: redis.asyncio.Redis | None, vaga: _Vaga
) -> None:
    """Libera a vaga e as conexões; é idempotente e roda mesmo se o fluxo nunca começou."""
    vaga.liberar()
    with anyio.CancelScope(shield=True):
        await _fechar(pubsub, cliente)


async def _fechar(pubsub: PubSub | None, cliente: redis.asyncio.Redis | None) -> None:
    for alvo in (pubsub, cliente):
        if alvo is None:
            continue
        try:
            await alvo.aclose()
        except Exception as erro:
            logger.warning(f"Falha ao fechar a conexão do fluxo: {type(erro).__name__}")


def _token_da_requisicao(requisicao: Request) -> SessaoToken:
    try:
        return validar_token(
            requisicao.cookies.get(NOME_COOKIE, ""), config_auth.JWT_SECRET.get_secret_value()
        )
    except TokenInvalido:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Não autenticado.") from None


@router.get("/analises/{analise_id}/eventos")
async def acompanhar_analise(
    analise_id: uuid.UUID,
    requisicao: Request,
    usuario: Annotated[Usuario, Depends(usuario_atual)],
    sessao: Annotated[Session, Depends(obter_sessao)],
    fabrica_sessao: Annotated[sessionmaker[Session], Depends(obter_fabrica_sessao)],
    fabrica_redis: Annotated[
        Callable[[], redis.asyncio.Redis], Depends(obter_fabrica_redis_assincrono)
    ],
) -> StreamingResponse:
    token = _token_da_requisicao(requisicao)
    vaga = _reservar(usuario.id)
    cliente = pubsub = None
    try:
        cliente = fabrica_redis()
        pubsub = cliente.pubsub()
        # A inscrição precede a leitura do estado: nenhum evento se perde entre as duas.
        with anyio.fail_after(TIMEOUT_REDIS_S):
            await pubsub.subscribe(canal(usuario.id, analise_id))
        estado = await run_in_threadpool(_ler_estado, sessao, analise_id, usuario.id)
        if estado is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Análise não encontrada.")
    except (RedisError, TimeoutError) as erro:
        await _encerrar(pubsub, cliente, vaga)
        logger.error(f"Redis indisponível ao abrir o fluxo: {type(erro).__name__}")
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Acompanhamento indisponível."
        ) from None
    except BaseException:
        await _encerrar(pubsub, cliente, vaga)
        raise
    return StreamingResponse(
        _fluxo(pubsub, cliente, estado, analise_id, token, fabrica_sessao, vaga),
        media_type="text/event-stream; charset=utf-8",
        headers=CABECALHOS_SSE,
        background=BackgroundTask(_encerrar, pubsub, cliente, vaga),
    )
