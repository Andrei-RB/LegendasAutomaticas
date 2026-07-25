import os
from fastapi import UploadFile, HTTPException, status
from app.core.config import settings
from app.core.logger import logger

async def validate_video_file(arquivo_upload: UploadFile):
    """
    Motor principal de triagem e sanitização para entradas externas:
    Bloqueio de Path Traversal, Filtro estrito de extensões e limites volumétricos.
    """
    if arquivo_upload is None or arquivo_upload.filename == "":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Estrutura de arquivo rejeitada: Payload nulo."
        )

    # MITIGAÇÃO: Validação rígida contra manipulação de nomes de diretório (Path Traversal / LFI)
    nome_arquivo_seguro = os.path.basename(arquivo_upload.filename)
    if not nome_arquivo_seguro:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Violação de segurança detectada: Formatação de nome de arquivo nociva."
        )
    
    _, formato_extensao = os.path.splitext(nome_arquivo_seguro)
    formato_extensao = formato_extensao.lower()

    # MITIGAÇÃO: Lista Branca estrita de tipos de arquivo (OWASP Top 10)
    if formato_extensao not in settings.allowed_extensions_list:
        logger.warning(f"Auditoria de Risco: Arquivo bloqueado com extensão letal/proibida: {formato_extensao} - Origem: {nome_arquivo_seguro}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bloqueio Sistêmico: Arquivos do tipo {formato_extensao} são estritamente vetados."
        )

    # MITIGAÇÃO SECUNDÁRIA: Verificação mecânica profunda de peso após barreira do Middleware
    arquivo_upload.file.seek(0, 2) 
    peso_bytes_verificado = arquivo_upload.file.tell() 
    arquivo_upload.file.seek(0) 

    if peso_bytes_verificado > settings.MAX_UPLOAD_SIZE:
        logger.warning(f"Auditoria de Risco: Violação de quota de armazenamento. Peso recebido: {peso_bytes_verificado} bytes - Limite Restritivo: {settings.MAX_UPLOAD_SIZE}")
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Transação cancelada: Volume máximo de ingestão de dados excedido por norma de segurança."
        )
    
    return True
