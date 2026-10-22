import logging
import os
from logging.handlers import RotatingFileHandler

from pythonjsonlogger.json import JsonFormatter

from app.nucleo.config import settings


def configurar_logging() -> logging.Logger:
    registro = logging.getLogger("app")
    registro.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
    registro.propagate = False

    if not registro.handlers:
        # Arquivo em JSON com rotação limita o uso de disco; console em texto simples.
        arquivo = RotatingFileHandler(
            os.path.join(settings.LOG_DIR, "app.log"), maxBytes=10 * 1024 * 1024, backupCount=5
        )
        arquivo.setFormatter(JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        registro.addHandler(arquivo)

        console = logging.StreamHandler()
        console.setFormatter(
            logging.Formatter("[%(asctime)s] %(levelname)s em %(module)s: %(message)s")
        )
        registro.addHandler(console)

    return registro


logger = configurar_logging()
