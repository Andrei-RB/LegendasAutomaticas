from dataclasses import dataclass

from celery.exceptions import SoftTimeLimitExceeded

from app.pipeline.armazenamento import ErroArmazenamento
from app.pipeline.trava_gpu import TravaIndisponivel, TravaPerdida

# Mensagens fixas e sem dados da entrada: são as únicas que saem do servidor.
MENSAGENS: dict[str, str] = {
    "INTERNO": "Não foi possível concluir esta etapa. Tente novamente.",
    "ENTRADA_INVALIDA": "Os dados desta etapa são inválidos.",
    "ENTRADA_AUSENTE": "Falta o resultado de uma etapa anterior. Refaça a análise a partir dela.",
    "ARMAZENAMENTO": "Falha ao ler ou gravar os arquivos da análise.",
    "GPU_INDISPONIVEL": "A placa de vídeo está ocupada. Tente novamente em instantes.",
    "TEMPO_ESGOTADO": "A etapa excedeu o tempo limite.",
    "ETAPA_DESCONHECIDA": "Etapa de processamento desconhecida.",
    "ANALISE_INEXISTENTE": "Análise não encontrada.",
}


@dataclass(frozen=True)
class ErroPublico:
    codigo: str
    mensagem: str


class ErroPipeline(Exception):
    """Falha esperada do pipeline; `detalhe` é apenas para o log e nunca sai na mensagem."""

    def __init__(self, codigo: str, detalhe: str = "") -> None:
        if codigo not in MENSAGENS:
            raise ValueError("código de erro desconhecido")
        super().__init__(MENSAGENS[codigo])
        self.codigo = codigo
        self.mensagem = MENSAGENS[codigo]
        self.detalhe = detalhe

    def __str__(self) -> str:
        return self.mensagem


def traduzir(erro: BaseException) -> ErroPublico:
    if isinstance(erro, ErroPipeline):
        codigo = erro.codigo
    elif isinstance(erro, TravaIndisponivel | TravaPerdida):
        codigo = "GPU_INDISPONIVEL"
    elif isinstance(erro, SoftTimeLimitExceeded | TimeoutError):
        codigo = "TEMPO_ESGOTADO"
    elif isinstance(erro, ErroArmazenamento | OSError):
        codigo = "ARMAZENAMENTO"
    else:
        codigo = "INTERNO"
    return ErroPublico(codigo=codigo, mensagem=MENSAGENS[codigo])
