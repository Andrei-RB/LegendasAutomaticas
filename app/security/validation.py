import os
from fastapi import UploadFile, HTTPException, status
from app.core.config import settings
from app.core.logger import logger

async def validate_video_file(file: UploadFile):
    """
    Validates uploaded file against path traversal, extensions, and size limits to prevent abuse.
    """
    if file is None or file.filename == "":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Nenhum arquivo enviado."
        )

    # Validate against malicious filenames (Path Traversal)
    safe_filename = os.path.basename(file.filename)
    if not safe_filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nome de arquivo inválido."
        )
    
    # Extract extension
    _, ext = os.path.splitext(safe_filename)
    ext = ext.lower()

    # Verify Extension (OWASP: File Upload Protection)
    if ext not in settings.allowed_extensions_list:
        logger.warning(f"Extensão não permitida: {ext} - Arquivo: {safe_filename}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Extensão de arquivo {ext} não permitida."
        )

    # Size Verification (Note: File length requires loading to memory/buffer in streaming)
    # Basic size validation by inspecting spool size if possible, or enforcing via web server max bounds.
    file.file.seek(0, 2) # Move to end
    file_size = file.file.tell() # Get size
    file.file.seek(0) # Reset to beginning

    if file_size > settings.MAX_UPLOAD_SIZE:
        logger.warning(f"Arquivo excedeu o limite máximo: {file_size} bytes - Limite: {settings.MAX_UPLOAD_SIZE}")
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Arquivo muito grande. Limite é de 500 MB."
        )
    
    return True
