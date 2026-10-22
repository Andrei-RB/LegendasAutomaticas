import os
from typing import Any, TextIO

from app.midia.srt import formatar_timestamp
from app.nucleo.config import settings
from app.nucleo.logger import logger

_modelo = None


def carregar_modelo() -> Any:
    global _modelo
    if _modelo is None:
        # Importação tardia: a dependência pesada só é carregada pelo worker que a usa.
        from faster_whisper import WhisperModel

        logger.info("Carregando o modelo faster-whisper (base, int8, CPU).")
        _modelo = WhisperModel("base", device="cpu", compute_type="int8")
    return _modelo


def _escrever_entrada(arquivo: TextIO, indice: int, inicio: float, fim: float, texto: str) -> None:
    arquivo.write(
        f"{indice}\n{formatar_timestamp(inicio)} --> {formatar_timestamp(fim)}\n{texto}\n\n"
    )


def transcrever_e_gerar_srt(caminho_audio: str, job_id: str, tarefa: Any = None) -> str:
    """Transcreve o áudio e grava um SRT com uma entrada por palavra."""
    modelo = carregar_modelo()

    logger.info(f"[{job_id}] Iniciando transcrição palavra a palavra.")
    segmentos, info = modelo.transcribe(caminho_audio, vad_filter=True, word_timestamps=True)

    caminho_srt = os.path.join(settings.OUTPUT_DIR, f"{job_id}.srt")
    duracao_total = info.duration

    with open(caminho_srt, "w", encoding="utf-8") as srt:
        indice = 1
        for segmento in segmentos:
            if tarefa and duracao_total > 0:
                progresso = 30 + int((segmento.end / duracao_total) * 60)
                andamento = f"({int(segmento.end)}s de {int(duracao_total)}s)"
                try:
                    tarefa.update_state(
                        state="PROCESSING",
                        meta={
                            "progress": progresso,
                            "status": f"Transcrevendo... {andamento}",
                        },
                    )
                except Exception as falha:
                    logger.warning(f"[{job_id}] Falha ao publicar progresso: {falha}")

            palavras = getattr(segmento, "words", None)
            if palavras is None:
                texto = segmento.text.strip()
                if texto:
                    _escrever_entrada(srt, indice, segmento.start, segmento.end, texto)
                    indice += 1
                continue

            for palavra in palavras:
                texto = palavra.word.strip()
                if texto:
                    _escrever_entrada(srt, indice, palavra.start, palavra.end, texto)
                    indice += 1

    logger.info(f"[{job_id}] Transcrição finalizada: {caminho_srt}.")
    return caminho_srt
