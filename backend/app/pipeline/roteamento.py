from typing import Any

from app.pipeline.registro import registro_padrao

NOME_TAREFA_ETAPA = "pipeline.executar_etapa"


def rotear_tarefa(nome: str, args: Any, kwargs: Any, *_: Any, **__: Any) -> dict[str, str] | None:
    """Envia a tarefa de etapa à fila declarada no registro; as demais seguem a fila padrão."""
    if nome != NOME_TAREFA_ETAPA:
        return None
    etapa = (kwargs or {}).get("etapa")
    if etapa not in registro_padrao:
        return None
    return {"queue": registro_padrao.obter(etapa).fila}
