import contextlib
import os
import shutil
import uuid
from typing import Annotated, BinaryIO

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.esquemas.job import JobError, JobResponse, JobStatus
from app.modelos.usuario import Usuario
from app.modelos.video import Video
from app.nucleo.config import settings
from app.nucleo.dependencias import obter_sessao, usuario_atual
from app.nucleo.logger import logger
from app.nucleo.validacao import job_id_valido, validar_arquivo_video
from app.workers.tasks import MENSAGEM_FALHA, process_video_task

router = APIRouter()


def _validar_job_id(job_id: str) -> None:
    if not job_id_valido(job_id):
        logger.warning(f"Identificador inválido: {job_id[:64]!r}")
        raise HTTPException(status_code=400, detail="ID Invalido")


def _registrar_video(sessao: Session, job_id: str, user_id: uuid.UUID, caminho: str) -> None:
    sessao.add(
        Video(id=uuid.UUID(job_id), user_id=user_id, origem="upload", caminho_original=caminho)
    )
    sessao.commit()


def _remover_registro(sessao: Session, job_id: str, user_id: uuid.UUID) -> None:
    sessao.rollback()
    video = _buscar_video(sessao, job_id, user_id)
    if video is not None:
        sessao.delete(video)
        sessao.commit()


def _buscar_video(sessao: Session, job_id: str, user_id: uuid.UUID) -> Video | None:
    return sessao.scalar(
        select(Video).where(Video.id == uuid.UUID(job_id), Video.user_id == user_id)
    )


def _exigir_video(sessao: Session, job_id: str, user_id: uuid.UUID) -> None:
    if _buscar_video(sessao, job_id, user_id) is None:
        raise HTTPException(status_code=404, detail="Job não encontrado.")


def _remover_arquivo(caminho: str) -> None:
    with contextlib.suppress(FileNotFoundError):
        os.remove(caminho)


def _gravar_arquivo(origem: BinaryIO, caminho: str) -> None:
    with open(caminho, "wb") as destino:
        shutil.copyfileobj(origem, destino)


@router.post(
    "/upload-video",
    response_model=JobResponse,
    responses={400: {"model": JobError}, 413: {"model": JobError}},
)
async def upload_video(
    file: Annotated[UploadFile, File()],
    usuario: Annotated[Usuario, Depends(usuario_atual)],
    sessao: Annotated[Session, Depends(obter_sessao)],
):
    await validar_arquivo_video(file)

    job_id = str(uuid.uuid4())
    extensao = os.path.splitext(file.filename)[1]
    nome_seguro = f"{job_id}{extensao}"
    caminho = os.path.join(settings.UPLOAD_DIR, nome_seguro)

    logger.info(f"Upload recebido: {job_id} ({extensao.lower()})")

    try:
        await run_in_threadpool(_gravar_arquivo, file.file, caminho)
    except Exception as erro:
        logger.error(f"Falha ao salvar o vídeo {job_id}: {erro}")
        raise HTTPException(
            status_code=500, detail="Erro interno ao salvar arquivo. Tente novamente."
        ) from erro

    try:
        await run_in_threadpool(_registrar_video, sessao, job_id, usuario.id, caminho)
    except Exception as erro:
        logger.error(f"Falha ao registrar o vídeo {job_id}: {type(erro).__name__}")
        await run_in_threadpool(_remover_arquivo, caminho)
        raise HTTPException(
            status_code=500, detail="Erro interno ao salvar arquivo. Tente novamente."
        ) from erro

    try:
        tarefa = process_video_task.apply_async(args=[caminho, job_id], task_id=job_id)
        logger.info(f"Tarefa criada: {tarefa.id}")
    except Exception as erro:
        logger.error(f"Falha ao enfileirar a tarefa (Redis indisponível?): {erro}")
        await run_in_threadpool(_remover_arquivo, caminho)
        await run_in_threadpool(_remover_registro, sessao, job_id, usuario.id)
        raise HTTPException(status_code=503, detail="Fila de processamento offline.") from erro

    return JobResponse(
        job_id=job_id,
        status="PENDING",
        message="Upload recebido! Vídeo na fila para processamento de legendas.",
    )


@router.get("/upload-video", dependencies=[Depends(usuario_atual)])
async def upload_video_get():
    raise HTTPException(
        status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
        detail="Método não permitido. Você deve enviar via POST (Upload) com os dados do arquivo.",
    )


@router.get("/status/{job_id}", response_model=JobStatus)
async def get_status(
    job_id: str,
    usuario: Annotated[Usuario, Depends(usuario_atual)],
    sessao: Annotated[Session, Depends(obter_sessao)],
):
    _validar_job_id(job_id)
    await run_in_threadpool(_exigir_video, sessao, job_id, usuario.id)
    tarefa = process_video_task.AsyncResult(job_id)

    if tarefa.state == "PENDING":
        return JobStatus(job_id=job_id, status="PENDING", progress=0)
    if tarefa.state == "FAILURE":
        # Nunca repassar str(tarefa.info): pode conter caminhos e detalhes internos.
        return JobStatus(job_id=job_id, status="FAILURE", progress=0, error=MENSAGEM_FALHA)
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
async def download_srt(
    job_id: str,
    usuario: Annotated[Usuario, Depends(usuario_atual)],
    sessao: Annotated[Session, Depends(obter_sessao)],
):
    _validar_job_id(job_id)
    await run_in_threadpool(_exigir_video, sessao, job_id, usuario.id)

    caminho_srt = os.path.join(settings.OUTPUT_DIR, f"{job_id}.srt")
    if not await run_in_threadpool(os.path.exists, caminho_srt):
        raise HTTPException(
            status_code=404, detail="Arquivo de legenda não encontrado ou não finalizado."
        )

    return FileResponse(
        caminho_srt,
        media_type="text/plain",
        filename=f"legenda_{job_id}.srt",
    )
