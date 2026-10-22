import os

from celery.exceptions import Ignore, SoftTimeLimitExceeded

from app.midia.ffmpeg import extrair_audio
from app.midia.transcricao import transcrever_e_gerar_srt
from app.nucleo.logger import logger
from app.workers.celery_app import celery_app


@celery_app.task(bind=True, name="process_video_task", soft_time_limit=3600, time_limit=3660)
def process_video_task(self, caminho_video: str, job_id: str):
    logger.info(f"[{job_id}] Início da tarefa: {caminho_video}")
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
        self.update_state(
            state="FAILURE", meta={"progress": 0, "status": "Erro: tempo limite excedido."}
        )
        raise Ignore() from None
    except Exception as erro:
        logger.error(f"[{job_id}] Erro: {erro}")
        self.update_state(state="FAILURE", meta={"progress": 0, "status": f"Erro: {erro}"})
        raise Ignore() from None
    finally:
        # Remove temporários em qualquer desfecho para não acumular disco.
        for temporario in (caminho_audio, caminho_video):
            if temporario and os.path.exists(temporario):
                try:
                    os.remove(temporario)
                except OSError as falha:
                    logger.error(f"[{job_id}] Falha ao remover {temporario}: {falha}")
