"""Exporta o OpenAPI da API para um arquivo JSON determinístico, sem subir o servidor."""

import json
import logging
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
# Valor fictício apenas para a importação do app; o esquema não depende do segredo.
SEGREDO_FICTICIO = "x" * 48


def exportar(destino: Path) -> None:
    destino = destino.resolve()
    origem = Path.cwd()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temporario:
        for chave in ("UPLOAD_DIR", "OUTPUT_DIR", "LOG_DIR", "DADOS_DIR"):
            os.environ[chave] = str(Path(temporario) / chave.lower())
        os.environ.update(
            {"JWT_SECRET": SEGREDO_FICTICIO, "APP_ENV": "production", "DEBUG": "false"}
        )
        # O cwd temporário impede a leitura de um .env local pelas configurações.
        os.chdir(temporario)
        sys.path.insert(0, str(RAIZ / "backend"))
        from app.main import app

        esquema = app.openapi()
        logging.shutdown()
        os.chdir(origem)
    texto = json.dumps(esquema, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(texto.encode("utf-8"))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("uso: python scripts/exportar_openapi.py <destino.json>")
    exportar(Path(sys.argv[1]))
