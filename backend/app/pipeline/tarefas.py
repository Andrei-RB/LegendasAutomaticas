import math
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any

from celery import Task
from celery.result import AsyncResult
from redis import Redis

from app.nucleo.banco import criar_fabrica_sessao, criar_motor
from app.nucleo.config import settings
from app.nucleo.logger import logger
from app.pipeline.armazenamento import ArmazenamentoLocal
from app.pipeline.erros import ErroPipeline
from app.pipeline.executor import ExecutorPipeline
from app.pipeline.registro import registro_padrao
from app.pipeline.roteamento import NOME_TAREFA_ETAPA
from app.workers.celery_app import celery_app

TIMEOUT_REDIS_S = 5
FOLGA_LIMITE_RIGIDO_S = 60
ESPERA_MIN_REAGENDAMENTO_S = 5
ESPERA_MAX_REAGENDAMENTO_S = 60
MAX_REAGENDAMENTOS = 200


@lru_cache(maxsize=1)
def obter_executor() -> ExecutorPipeline:
    """Monta o executor no primeiro uso, já dentro do processo filho do worker."""
    fabrica = criar_fabrica_sessao(criar_motor(settings.DATABASE_URL.get_secret_value()))
    redis = Redis.from_url(
        settings.REDIS_URL,
        socket_timeout=TIMEOUT_REDIS_S,
        socket_connect_timeout=TIMEOUT_REDIS_S,
        health_check_interval=30,
    )
    return ExecutorPipeline(
        fabrica, redis, ArmazenamentoLocal(Path(settings.DADOS_DIR)), registro_padrao
    )


def _uuid_canonico(texto: object) -> uuid.UUID | None:
    if not isinstance(texto, str):
        return None
    try:
        valor = uuid.UUID(texto)
    except ValueError:
        return None
    return valor if str(valor) == texto else None


def _recusada(codigo: str) -> dict[str, Any]:
    return {"status": "recusada", "codigo": codigo}


@celery_app.task(
    bind=True,
    name=NOME_TAREFA_ETAPA,
    max_retries=MAX_REAGENDAMENTOS,
    acks_late=True,
    reject_on_worker_lost=True,
    soft_time_limit=3600,
    time_limit=3600 + FOLGA_LIMITE_RIGIDO_S,
)
def executar_etapa_task(self: Task, analise_id: str, user_id: str, etapa: str) -> dict[str, Any]:
    # Os argumentos vêm do broker: são validados antes de qualquer acesso a banco ou disco.
    analise = _uuid_canonico(analise_id)
    usuario = _uuid_canonico(user_id)
    if analise is None or usuario is None:
        logger.error("Tarefa de etapa recusada: identificador inválido.")
        return _recusada("ENTRADA_INVALIDA")
    if etapa not in registro_padrao:
        logger.error("Tarefa de etapa recusada: etapa fora do registro.")
        return _recusada("ETAPA_DESCONHECIDA")
    try:
        resultado = obter_executor().executar(analise, usuario, etapa)
    except ErroPipeline as erro:
        return {"status": "falhou", "codigo": erro.codigo}
    except Exception as erro:
        # Nada da exceção vai ao result backend: o detalhe fica só no log do worker.
        logger.error(f"Tarefa de etapa falhou: {type(erro).__name__}")
        return {"status": "falhou", "codigo": "INTERNO"}
    if resultado.status == "em_execucao" and self.request.retries < MAX_REAGENDAMENTOS:
        # Reentrega de um worker que caiu: espera o lease vencer para assumir a linha.
        espera = math.ceil(resultado.lease_restante_s) + 1
        raise self.retry(
            countdown=min(max(espera, ESPERA_MIN_REAGENDAMENTO_S), ESPERA_MAX_REAGENDAMENTO_S)
        )
    return {"status": resultado.status, "hash_entrada": resultado.hash_entrada}


def enfileirar_etapa(analise_id: uuid.UUID, user_id: uuid.UUID, etapa: str) -> AsyncResult:
    definicao = registro_padrao.obter(etapa)
    return celery_app.send_task(
        NOME_TAREFA_ETAPA,
        kwargs={"analise_id": str(analise_id), "user_id": str(user_id), "etapa": etapa},
        queue=definicao.fila,
        soft_time_limit=definicao.limite_s,
        time_limit=definicao.limite_s + FOLGA_LIMITE_RIGIDO_S,
    )
