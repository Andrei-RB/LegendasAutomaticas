from celery import Celery
from app.core.config import settings

# Inicia cliente Celery conectado ao Redis
celery_app = Celery(
    "worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.workers.tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_track_started=True,
    worker_send_task_events=True,
    # Tempo em que o resultado fica no redis (1h)
    result_expires=3600,
)
