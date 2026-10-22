import os
import shutil
import uuid
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

from app.esquemas.job import JobError, JobResponse, JobStatus
from app.nucleo.config import settings
from app.nucleo.logger import logger
from app.nucleo.validacao import validar_arquivo_video
from app.workers.tasks import process_video_task

router = APIRouter()


def _gravar_arquivo(origem, caminho: str) -> None:
    with open(caminho, "wb") as destino:
        shutil.copyfileobj(origem, destino)


@router.post(
    "/upload-video",
    response_model=JobResponse,
    responses={400: {"model": JobError}, 413: {"model": JobError}},
)
async def upload_video(file: Annotated[UploadFile, File()]):
    await validar_arquivo_video(file)

    job_id = str(uuid.uuid4())
    extensao = os.path.splitext(file.filename)[1]
    nome_seguro = f"{job_id}{extensao}"
    caminho = os.path.join(settings.UPLOAD_DIR, nome_seguro)

    logger.info(f"Upload recebido: '{file.filename}' -> '{nome_seguro}'")

    try:
        await run_in_threadpool(_gravar_arquivo, file.file, caminho)
    except Exception as erro:
        logger.error(f"Falha ao salvar o vídeo {job_id}: {erro}")
        raise HTTPException(
            status_code=500, detail="Erro interno ao salvar arquivo. Tente novamente."
        ) from erro

    try:
        tarefa = process_video_task.apply_async(args=[caminho, job_id], task_id=job_id)
        logger.info(f"Tarefa criada: {tarefa.id}")
    except Exception as erro:
        logger.error(f"Falha ao enfileirar a tarefa (Redis indisponível?): {erro}")
        if os.path.exists(caminho):
            os.remove(caminho)
        raise HTTPException(status_code=503, detail="Fila de processamento offline.") from erro

    return JobResponse(
        job_id=job_id,
        status="PENDING",
        message="Upload recebido! Vídeo na fila para processamento de legendas.",
    )


@router.get("/upload-video")
async def upload_video_get():
    raise HTTPException(
        status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
        detail="Método não permitido. Envie o vídeo via POST.",
    )


@router.get("/status/{job_id}", response_model=JobStatus)
async def get_status(job_id: str):
    tarefa = process_video_task.AsyncResult(job_id)

    if tarefa.state == "PENDING":
        return JobStatus(job_id=job_id, status="PENDING", progress=0)
    if tarefa.state == "FAILURE":
        mensagem = str(tarefa.info) if tarefa.info else "Erro de execução."
        return JobStatus(job_id=job_id, status="FAILURE", progress=0, error=mensagem)
    if tarefa.state in ("PROCESSING", "SUCCESS"):
        meta = tarefa.info if isinstance(tarefa.info, dict) else {}
        return JobStatus(
            job_id=job_id,
            status=meta.get("status", tarefa.state),
            progress=meta.get("progress", 0),
            result_url=meta.get("result_url"),
        )
    return JobStatus(job_id=job_id, status=tarefa.state, progress=0)


@router.get("/download/{job_id}")
async def download_srt(job_id: str):
    # O identificador compõe o caminho do arquivo: só alfanumérico e hífen evita path traversal.
    if not job_id.replace("-", "").isalnum():
        logger.warning(f"Identificador inválido em download: {job_id!r}")
        raise HTTPException(status_code=400, detail="ID inválido")

    caminho_srt = os.path.join(settings.OUTPUT_DIR, f"{job_id}.srt")
    if not os.path.exists(caminho_srt):
        raise HTTPException(
            status_code=404, detail="Arquivo de legenda não encontrado ou não finalizado."
        )

    return FileResponse(
        caminho_srt,
        media_type="text/plain",
        filename=f"legenda_{job_id}.srt",
    )
