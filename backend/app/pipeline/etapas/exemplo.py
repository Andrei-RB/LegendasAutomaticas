import hashlib

from app.pipeline.executor import ContextoPasso, Etapa, Passo
from app.pipeline.hashing import canonizar


def _passo(etapa: str, numero: int) -> Passo:
    saida = f"{etapa}_p{numero}.json"
    anterior = f"{etapa}_p{numero - 1}.json" if numero > 1 else None

    def executar(contexto: ContextoPasso) -> None:
        sha_anterior = hashlib.sha256(contexto.ler(anterior)).hexdigest() if anterior else None
        contexto.gravar(
            saida,
            canonizar(
                {
                    "passo": numero,
                    "semente": contexto.parametros.get("semente"),
                    "anterior": sha_anterior,
                }
            ),
        )

    return Passo(nome=f"p{numero}", saidas=(saida,), executar=executar)


def _etapa(nome: str, fila: str, *, usa_gpu: bool) -> Etapa:
    return Etapa(
        nome=nome,
        versao=1,
        fila=fila,  # type: ignore[arg-type]
        passos=tuple(_passo(nome, n) for n in (1, 2, 3)),
        parametros=("semente",),
        usa_gpu=usa_gpu,
        limite_s=300,
    )


EXEMPLO = _etapa("exemplo", "cpu", usa_gpu=False)
EXEMPLO_GPU = _etapa("exemplo_gpu", "gpu", usa_gpu=True)
