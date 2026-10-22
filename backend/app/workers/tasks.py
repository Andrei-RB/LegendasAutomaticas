import os

from celery.exceptions import Ignore, SoftTimeLimitExceeded

from app.midia.ffmpeg import extrair_audio
from app.midia.transcricao import transcrever_e_gerar_srt
from app.nucleo.config import settings
from app.nucleo.logger import logger
from app.workers.celery_app import celery_app

MENSAGEM_FALHA = "Falha no processamento do vídeo."
MENSAGEM_TEMPO_LIMITE = "Tempo limite de processamento excedido."


def meta_falha(mensagem: str) -> dict:
    # O Celery exige exc_type no estado FAILURE; sem ele a leitura do estado levanta ValueError.
    return {
        "exc_type": "ErroProcessamento",
        "exc_message": [mensagem],
        "progress": 0,
        "status": mensagem,
    }


def _dentro_do_upload(caminho: str) -> bool:
    base = os.path.realpath(settings.UPLOAD_DIR)
    try:
        return os.path.commonpath([base, os.path.realpath(caminho)]) == base
    except ValueError:
        return False


@celery_app.task(bind=True, name="process_video_task", soft_time_limit=3600, time_limit=3660)
def process_video_task(self, caminho_video: str, job_id: str) -> dict[str, str]:
    # O caminho vem do broker: nunca ler nem apagar fora do diretório de uploads.
    if not _dentro_do_upload(caminho_video):
        logger.error(f"[{job_id}] Caminho fora do diretório de uploads recusado.")
        self.update_state(state="FAILURE", meta=meta_falha(MENSAGEM_FALHA))
        raise Ignore()

    logger.info(f"[{job_id}] Início da tarefa.")
    self.update_state(
        state="PROCESSING", meta={"progress": 5, "status": "Iniciando extração de áudio..."}
    )

    caminho_audio = None
    try:
        caminho_audio = extrair_audio(caminho_video, job_id)
        self.update_state(
            state="PROCESSING",
            meta={"progress": 20, "status": "Áudio extraído. Carregando modelo..."},
        )

        transcrever_e_gerar_srt(caminho_audio, job_id, self)

        url_resultado = f"/api/v1/download/{job_id}"
        self.update_state(
            state="SUCCESS",
            meta={
                "progress": 100,
                "status": "Legenda gerada com sucesso!",
                "result_url": url_resultado,
            },
        )
        logger.info(f"[{job_id}] Tarefa concluída.")
        return {"status": "Completed", "result_url": url_resultado}

    except SoftTimeLimitExceeded:
        logger.error(f"[{job_id}] Tempo limite excedido.")
        self.update_state(state="FAILURE", meta=meta_falha(MENSAGEM_TEMPO_LIMITE))
        raise Ignore() from None
    except Exception as erro:
        # O detalhe fica só no log; ao cliente vai uma mensagem fixa.
        logger.error(f"[{job_id}] Erro: {erro}")
        self.update_state(state="FAILURE", meta=meta_falha(MENSAGEM_FALHA))
        raise Ignore() from None
    finally:
        # Remove temporários em qualquer desfecho para não acumular disco.
        for temporario in (caminho_audio, caminho_video):
            if temporario and os.path.exists(temporario):
                try:
                    os.remove(temporario)
                except OSError as falha:
                    logger.error(f"[{job_id}] Falha ao remover {temporario}: {falha}")
