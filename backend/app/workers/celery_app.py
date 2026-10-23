from celery import Celery
from kombu import Queue

from app.nucleo.config import settings
from app.pipeline.roteamento import rotear_tarefa

FILAS = ("celery", "gpu", "cpu", "ai", "render")
# Acima do maior limite de tempo de uma etapa, para que a entrega não seja repetida em execução.
VISIBILITY_TIMEOUT_S = 7500

celery_app = Celery(
    "worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.workers.tasks", "app.pipeline.tarefas"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_track_started=True,
    worker_send_task_events=True,
    result_expires=3600,
    task_default_queue="celery",
    task_queues=tuple(Queue(nome) for nome in FILAS),
    task_routes=(rotear_tarefa,),
    broker_transport_options={"visibility_timeout": VISIBILITY_TIMEOUT_S},
)
