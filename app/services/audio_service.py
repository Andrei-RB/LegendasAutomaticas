import subprocess
import os
from app.core.config import settings
from app.core.logger import logger

def extract_audio(video_path: str, job_id: str) -> str:
    """
    Extrai o áudio do vídeo focado no melhor formato para a Whisper (WAV 16kHz mono).
    """
    audio_filename = f"{job_id}.wav"
    audio_path = os.path.join(settings.UPLOAD_DIR, audio_filename)
    
    # FFmpeg command strictly structured. Subprocess array guards against Command Injection (OWASP).
    command = [
        "ffmpeg",
        "-y", # Overwrite outputs silently
        "-i", video_path, # Input
        "-vn", # Disable video
        "-acodec", "pcm_s16le", # WAV format expected by Whisper sometimes (or PCM)
        "-ar", "16000", # Sample rate to 16kHz
        "-ac", "1", # Mono audio
        audio_path
    ]
    
    try:
        logger.info(f"[{job_id}] Iniciando extração de áudio: {command}")
        # Run with check=True to raise exception on non-zero return code
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        return audio_path
    except subprocess.CalledProcessError as e:
        logger.error(f"[{job_id}] Erro no FFmpeg: {e.stderr}")
        raise RuntimeError("Falha ao extrair áudio do vídeo.")
    except FileNotFoundError:
        logger.error(f"[{job_id}] FFmpeg não encontrado no PATH.")
        raise RuntimeError("FFmpeg não configurado no servidor.")
