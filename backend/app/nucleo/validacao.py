import os

from fastapi import HTTPException, UploadFile, status

from app.nucleo.config import settings
from app.nucleo.logger import logger

BYTES_POR_MB = 1024 * 1024


def mensagem_limite_upload() -> str:
    return f"Arquivo muito grande. Limite é de {settings.MAX_UPLOAD_SIZE // BYTES_POR_MB} MB."


async def validar_arquivo_video(arquivo: UploadFile) -> bool:
    """Valida nome, extensão e tamanho do upload antes de gravar em disco."""
    if arquivo is None or not arquivo.filename:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Nenhum arquivo enviado.")

    nome_seguro = os.path.basename(arquivo.filename)
    if not nome_seguro:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Nome de arquivo inválido.")

    extensao = os.path.splitext(nome_seguro)[1].lower()
    if extensao not in settings.allowed_extensions_list:
        logger.warning(f"Extensão não permitida: {extensao!r}")
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail=f"Extensão de arquivo {extensao} não permitida."
        )

    arquivo.file.seek(0, os.SEEK_END)
    tamanho = arquivo.file.tell()
    arquivo.file.seek(0)

    if tamanho > settings.MAX_UPLOAD_SIZE:
        logger.warning(
            f"Upload acima do limite: {tamanho} bytes (máximo {settings.MAX_UPLOAD_SIZE})"
        )
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, detail=mensagem_limite_upload())

    return True
