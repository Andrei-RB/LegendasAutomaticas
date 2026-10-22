import os
import subprocess

from app.nucleo.config import settings
from app.nucleo.logger import logger

# O ffmpeg detecta o formato pelo conteúdo; restringir bloqueia playlist/concat com leitura externa.
FORMATOS_PERMITIDOS = "mov,mp4,m4a,3gp,3g2,mj2,matroska,webm,avi"


def montar_comando_audio(caminho_video: str, caminho_audio: str) -> list[str]:
    # Lista de argumentos sem shell; o prefixo file: impede que o caminho seja lido como URL.
    return [
        "ffmpeg",
        "-nostdin",
        "-y",
        "-protocol_whitelist",
        "file",
        "-format_whitelist",
        FORMATOS_PERMITIDOS,
        "-i",
        f"file:{caminho_video}",
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
        logger.info(f"[{job_id}] Extraindo áudio.")
        subprocess.run(  # noqa: S603
            comando,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=settings.FFMPEG_TIMEOUT_S,
        )
        return caminho_audio
    except subprocess.CalledProcessError as erro:
        logger.error(f"[{job_id}] Erro no FFmpeg: {erro.stderr}")
        raise RuntimeError("Falha ao extrair áudio do vídeo.") from erro
    except subprocess.TimeoutExpired as erro:
        logger.error(f"[{job_id}] FFmpeg excedeu {settings.FFMPEG_TIMEOUT_S}s.")
        raise RuntimeError("Tempo limite excedido na extração de áudio.") from erro
    except FileNotFoundError as erro:
        logger.error(f"[{job_id}] FFmpeg não encontrado no PATH.")
        raise RuntimeError("FFmpeg não configurado no servidor.") from erro
