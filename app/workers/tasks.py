import os
import time
from app.workers.celery_worker import celery_app
from app.services.audio_service import extract_audio
from app.services.transcription_service import transcribe_and_generate_srt
from app.core.logger import logger
from celery.exceptions import SoftTimeLimitExceeded, Ignore

@celery_app.task(bind=True, name="process_video_task", soft_time_limit=3600, time_limit=3660)
def process_video_task(self, video_path: str, job_id: str):
    logger.info(f"[{job_id}] INICIO TASK - path: {video_path}")
    self.update_state(state='PROCESSING', meta={'progress': 5, 'status': 'Iniciando extração de áudio...'})
    
    try:
        # 1. Extração de áudio
        audio_path = extract_audio(video_path, job_id)
        self.update_state(state='PROCESSING', meta={'progress': 20, 'status': 'Áudio extraído. Carregando modelo IA...'})
        
        # 2. Transcrição assíncrona (com progresso via stream updates internamente)
        srt_path = transcribe_and_generate_srt(audio_path, job_id, self)
        
        self.update_state(state='SUCCESS', meta={
            'progress': 100, 
            'status': 'Legenda gerada com sucesso!',
            'result_url': f"/api/v1/download/{job_id}"
        })
        
        # Limpeza do ambiente (remoção segura de temps para evitar disk bloat NIST)
        if os.path.exists(audio_path):
            os.remove(audio_path)
        if os.path.exists(video_path):
            os.remove(video_path)
            
        logger.info(f"[{job_id}] JOB PROCESSADO COM SUCESSO. ")
        
        return {'status': 'Completed', 'result_url': f"/api/v1/download/{job_id}"}
        
    except SoftTimeLimitExceeded:
        logger.error(f"[{job_id}] Timeout excedido na task de IA.")
        if os.path.exists(video_path): os.remove(video_path)
        self.update_state(state='FAILURE', meta={'progress': 0, 'status': 'Erro: Tempo limite excedido.'})
        raise Ignore()
    except Exception as e:
        logger.error(f"[{job_id}] ERRO: {str(e)}")
        # Cleanup
        if os.path.exists(video_path): os.remove(video_path)
        self.update_state(state='FAILURE', meta={'progress': 0, 'status': f'Erro: {str(e)}'})
        raise Ignore()
