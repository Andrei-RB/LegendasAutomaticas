import os
import uuid
import shutil
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from fastapi.responses import FileResponse
from app.core.config import settings
from app.core.logger import logger
from app.schemas.job import JobResponse, JobStatus, JobError
from app.security.validation import validate_video_file
from app.workers.tasks import process_video_task

router = APIRouter()

@router.post("/upload-video", response_model=JobResponse, responses={400: {"model": JobError}, 413: {"model": JobError}})
async def upload_video(file: UploadFile = File(...)):
    # Security Validation
    await validate_video_file(file)
    
    # Generate Unique Secure Identifier
    job_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1]
    secure_filename = f"{job_id}{ext}"
    file_path = os.path.join(settings.UPLOAD_DIR, secure_filename)
    
    logger.info(f"Realizando upload seguro: '{file.filename}' -> '{secure_filename}'")

    try:
        # Save file securely to local disk
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.error(f"Falha ao salvar o vídeo {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Erro interno ao salvar arquivo. Tente novamente.")
        
    # Dispatch Async Job via Celery
    try:
        logger.info(f"Enviando task processing no Celery para {job_id}.")
        task = process_video_task.apply_async(args=[file_path, job_id], task_id=job_id)
        logger.info(f"Task criada com id: {task.id}")
    except Exception as e:
        logger.error(f"Falha ao escalar task na fila Celery (Redis em baixo?): {str(e)}")
        # Delete broken file if queue is down
        if os.path.exists(file_path): os.remove(file_path)
        raise HTTPException(status_code=503, detail="Fila de processamento offline.")
    
    return JobResponse(
        job_id=job_id, 
        status="PENDING", 
        message="Upload recebido! Vídeo na fila para processamento de legendas."
    )

@router.get("/upload-video")
async def upload_video_get():
    logger.info("Acesso GET em /upload-video detectado.")
    raise HTTPException(
        status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
        detail="Método não permitido. Você deve enviar via POST (Upload) com os dados do arquivo."
    )

@router.get("/status/{job_id}", response_model=JobStatus)
async def get_status(job_id: str):
    # Retrieve state from Celery
    task = process_video_task.AsyncResult(job_id)
    
    if task.state == 'PENDING':
        return JobStatus(job_id=job_id, status="PENDING", progress=0)
    elif task.state == 'FAILURE':
        # Safely handle exception serialization
        error_msg = str(task.info) if task.info else "Erro de execução."
        return JobStatus(job_id=job_id, status="FAILURE", progress=0, error=error_msg)
    elif task.state in ['PROCESSING', 'SUCCESS']:
        # Extract meta
        meta = task.info if isinstance(task.info, dict) else {}
        return JobStatus(
            job_id=job_id,
            status=meta.get('status', task.state),
            progress=meta.get('progress', 0),
            result_url=meta.get('result_url')
        )
    else:
        # Default safety net
        return JobStatus(job_id=job_id, status=task.state, progress=0)

@router.get("/download/{job_id}")
async def download_srt(job_id: str):
    # Validate strictly job_id format to avert directory traversal
    if not job_id.replace('-', '').isalnum():
        logger.warning(f"Tentativa de Injeção em Download detectada com ID: {job_id}")
        raise HTTPException(status_code=400, detail="ID Invalido")
        
    srt_path = os.path.join(settings.OUTPUT_DIR, f"{job_id}.srt")
    
    if not os.path.exists(srt_path):
        raise HTTPException(status_code=404, detail="Arquivo de legenda não encontrado ou não finalizado.")
        
    return FileResponse(
        srt_path, 
        media_type="text/plain", 
        filename=f"legenda_{job_id}.srt",
        headers={"Content-Disposition": f"attachment; filename=legenda_{job_id}.srt"}
    )
