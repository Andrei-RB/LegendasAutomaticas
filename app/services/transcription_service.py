import os
from faster_whisper import WhisperModel
from app.core.config import settings
from app.core.logger import logger

model = None

def load_model():
    global model
    if model is None:
        logger.info("Carregando o modelo faster-whisper (tiny/base) na CPU/GPU...")
        # Usa compute_type int8 para economizar memoria e maximizar portabilidade em servidores menores
        model = WhisperModel("base", device="cpu", compute_type="int8")
        logger.info("Modelo carregado com sucesso.")
    return model

def format_timestamp(seconds: float) -> str:
    """Converte segundos para formato SRT: HH:MM:SS,mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def transcribe_and_generate_srt(audio_path: str, job_id: str, task_instance=None) -> str:
    """
    Usa o modelo Whisper para transcrever o áudio e gera um formato srt sequencial.
    """
    whisper_model = load_model()
    
    logger.info(f"[{job_id}] Iniciando transcrição (modo Palavra por Palavra).")
    # OWASP Note: Limiting compute constraints per task via model defaults
    segments, info = whisper_model.transcribe(audio_path, vad_filter=True, word_timestamps=True)
    
    srt_filename = f"{job_id}.srt"
    srt_filepath = os.path.join(settings.OUTPUT_DIR, srt_filename)
    
    # total duration is exposed if available, useful to calculate % progress
    total_duration = info.duration
    
    with open(srt_filepath, "w", encoding="utf-8") as srt_file:
        word_index = 1
        for segment in segments:
            # Emitir atualização de progresso caso executando no Celery (Avançamos o chunk visual)
            if task_instance and total_duration > 0:
                # Progress ranges from 30 to 90 during transcription
                progress = 30 + int((segment.end / total_duration) * 60)
                try: 
                    task_instance.update_state(state='PROCESSING', meta={'progress': progress, 'status': f'Transcrevendo... ({int(segment.end)}s de {int(total_duration)}s)'})
                except Exception:
                    pass

            # Verificação se o fallback clássico sem palavras foi inferido
            if getattr(segment, 'words', None) is None:
                start_time = format_timestamp(segment.start)
                end_time = format_timestamp(segment.end)
                text = segment.text.strip()
                
                if text:
                    srt_file.write(f"{word_index}\n")
                    srt_file.write(f"{start_time} --> {end_time}\n")
                    srt_file.write(f"{text}\n\n")
                    word_index += 1
            else:
                # Iteração focada Palavra-por-Palavra (Formato Viral/Shorts)
                for word_obj in segment.words:
                    start_time = format_timestamp(word_obj.start)
                    end_time = format_timestamp(word_obj.end)
                    text = word_obj.word.strip()
                    
                    if not text:
                        continue
                        
                    srt_file.write(f"{word_index}\n")
                    srt_file.write(f"{start_time} --> {end_time}\n")
                    srt_file.write(f"{text}\n\n")
                    word_index += 1

    logger.info(f"[{job_id}] Transcrição finalizada e SRT criado em {srt_filepath}.")
    return srt_filepath
