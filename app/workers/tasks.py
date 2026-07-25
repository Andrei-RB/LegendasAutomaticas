import os
import time
from app.workers.celery_worker import celery_app
from app.services.audio_service import extract_audio
from app.services.transcription_service import transcribe_and_generate_srt
from app.core.logger import logger
from celery.exceptions import SoftTimeLimitExceeded, Ignore

@celery_app.task(bind=True, name="process_video_task", soft_time_limit=3600, time_limit=3660)
def process_video_task(self, caminho_video: str, identificador_trabalho: str):
    logger.info(f"[{identificador_trabalho}] INÍCIO DA TAREFA DE PROCESSAMENTO ESTRITO - caminho: {caminho_video}")
    self.update_state(state='PROCESSING', meta={'progress': 5, 'status': 'Iniciando extração do canal de áudio...'})
    
    caminho_audio = None
    try:
        # Extração de fluxo de áudio seguro
        caminho_audio = extract_audio(caminho_video, identificador_trabalho)
        self.update_state(state='PROCESSING', meta={'progress': 20, 'status': 'Mídia extraída. Inicializando processamento neural IA...'})
        
        # Transcrição algorítmica
        caminho_srt = transcribe_and_generate_srt(caminho_audio, identificador_trabalho, self)
        
        self.update_state(state='SUCCESS', meta={
            'progress': 100, 
            'status': 'Algoritmo concluído e legendagem gerada e assinada com sucesso!',
            'result_url': f"/api/v1/download/{identificador_trabalho}"
        })
        
        logger.info(f"[{identificador_trabalho}] TRABALHO PROCESSADO COM EFICÁCIA.")
        return {'status': 'Concluído', 'result_url': f"/api/v1/download/{identificador_trabalho}"}
        
    except SoftTimeLimitExceeded:
        logger.error(f"[{identificador_trabalho}] Limite temporal de processamento IA estourado (Timeout).")
        self.update_state(state='FAILURE', meta={'progress': 0, 'status': 'Falha Técnica: Execução prolongada encerrada por segurança.'})
        raise Ignore()
    except Exception as erro_excecao:
        logger.error(f"[{identificador_trabalho}] ERRO CRÍTICO NA EXECUÇÃO: {str(erro_excecao)}")
        self.update_state(state='FAILURE', meta={'progress': 0, 'status': f'Falha Crítica: {str(erro_excecao)}'})
        raise Ignore()
    finally:
        # MITIGAÇÃO DE ARMAZENAMENTO (GARANTIA DE LIMPEZA DE ESTADO / ZERO TRACE)
        for arquivo_temporario in [caminho_audio, caminho_video]:
            if arquivo_temporario and os.path.exists(arquivo_temporario):
                try:
                    os.remove(arquivo_temporario)
                except OSError as falha_sistema:
                    logger.error(f"[{identificador_trabalho}] Falha arquitetural ao tentar remover rastro temporário em {arquivo_temporario}: {falha_sistema}")
