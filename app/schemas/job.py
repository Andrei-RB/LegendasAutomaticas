from pydantic import BaseModel, Field
from typing import Optional

class JobResponse(BaseModel):
    job_id: str = Field(..., description="ID único do processamento gerado com UUID4", min_length=36, max_length=36)
    status: str = Field(..., description="Status momentâneo do request (ex: PENDING)")
    message: str = Field(..., description="Mensagem de retorno humano-legível")

class JobStatus(BaseModel):
    job_id: str = Field(..., description="ID único do processamento gerado com UUID4", min_length=36, max_length=36)
    status: str = Field(..., description="Status atual da transcrição (ex: PROCESSING, SUCCESS, FAILURE)")
    progress: int = Field(default=0, description="Progresso de 0 a 100", ge=0, le=100)
    result_url: Optional[str] = Field(None, description="URL relativa para baixar a legenda em caso de sucesso")
    error: Optional[str] = Field(None, description="Se status for FAILURE, exibe o motivo humano-legível")

class JobError(BaseModel):
    detail: str = Field(..., description="Mensagem do erro")
