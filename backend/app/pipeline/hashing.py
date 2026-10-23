import hashlib
import json
from collections.abc import Mapping
from typing import Any


def canonizar(valor: Any) -> bytes:
    """Serializa em JSON UTF-8 com chaves ordenadas, para que o hash não dependa da ordem."""
    return json.dumps(
        valor, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def calcular_hash_entrada(
    etapa: str, versao: int, entradas: Mapping[str, str], parametros: Mapping[str, Any]
) -> str:
    estrutura = {
        "etapa": etapa,
        "versao": versao,
        "entradas": dict(entradas),
        "parametros": dict(parametros),
    }
    return hashlib.sha256(canonizar(estrutura)).hexdigest()
