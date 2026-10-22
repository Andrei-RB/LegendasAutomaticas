import os
import subprocess

from app.nucleo.config import settings
from app.nucleo.logger import logger


def montar_comando_audio(caminho_video: str, caminho_audio: str) -> list[str]:
    # Lista de argumentos (sem shell) impede injeção de comando; WAV mono 16 kHz é o formato do ASR.
    return [
        "ffmpeg",
        "-y",
        "-i",
        caminho_video,
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        "16000",
        "-ac",
        "1",
        caminho_audio,
    ]


def extrair_audio(caminho_video: str, job_id: str) -> str:
    caminho_audio = os.path.join(settings.UPLOAD_DIR, f"{job_id}.wav")
    comando = montar_comando_audio(caminho_video, caminho_audio)

    try:
        logger.info(f"[{job_id}] Extraindo áudio: {comando}")
        # Lista de argumentos sem shell: não há injeção de comando.
        subprocess.run(  # noqa: S603
            comando, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True
        )
        return caminho_audio
    except subprocess.CalledProcessError as erro:
        logger.error(f"[{job_id}] Erro no FFmpeg: {erro.stderr}")
        raise RuntimeError("Falha ao extrair áudio do vídeo.") from erro
    except FileNotFoundError as erro:
        logger.error(f"[{job_id}] FFmpeg não encontrado no PATH.")
        raise RuntimeError("FFmpeg não configurado no servidor.") from erro
