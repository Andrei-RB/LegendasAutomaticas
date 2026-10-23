import re
from pathlib import Path

from alembic.config import Config

from alembic import command
from app.nucleo.config import settings
from app.nucleo.papeis import aplicar_papel_app, validar_senha

RAIZ_BACKEND = Path(__file__).resolve().parents[2]
_HEXADECIMAL = re.compile(r"[0-9a-f]{16,}")


def main() -> None:
    senha = settings.SENHA_PAPEL_APP.get_secret_value()
    if not senha:
        raise ValueError("SENHA_PAPEL_APP não definida")
    if not _HEXADECIMAL.fullmatch(senha):
        raise ValueError("SENHA_PAPEL_APP deve ser hexadecimal (entra em URLs)")
    validar_senha(senha)
    config = Config(str(RAIZ_BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(RAIZ_BACKEND / "alembic"))
    command.upgrade(config, "head")
    aplicar_papel_app(settings.DATABASE_URL.get_secret_value(), senha)


if __name__ == "__main__":
    main()
