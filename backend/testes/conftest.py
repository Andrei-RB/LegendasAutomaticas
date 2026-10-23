import os
import tempfile
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

# Ambiente fixado antes de qualquer import de app, para ignorar o .env local.
_BASE = Path(tempfile.mkdtemp(prefix="viraliza_testes_"))
os.environ["UPLOAD_DIR"] = str(_BASE / "uploads")
os.environ["OUTPUT_DIR"] = str(_BASE / "saidas")
os.environ["LOG_DIR"] = str(_BASE / "logs")
os.environ["DEBUG"] = "false"
os.environ["APP_ENV"] = "development"
os.environ["CORS_ORIGINS"] = ""
os.environ["MAX_UPLOAD_SIZE"] = str(1024 * 1024 * 1024)
os.environ["ALLOWED_EXTENSIONS"] = ".mp4,.avi,.mov,.mkv"

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def cliente():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


RAIZ_BACKEND = Path(__file__).resolve().parents[1]


@contextmanager
def _banco_efemero(url_admin: str) -> Iterator[str]:
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    nome = f"viraliza_teste_{uuid.uuid4().hex}"
    admin = create_engine(url_admin, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as con:
            con.execute(text(f'CREATE DATABASE "{nome}"'))
        try:
            yield make_url(url_admin).set(database=nome).render_as_string(hide_password=False)
        finally:
            with admin.connect() as con:
                con.execute(text(f'DROP DATABASE IF EXISTS "{nome}" WITH (FORCE)'))
    finally:
        admin.dispose()


@pytest.fixture(scope="session")
def url_admin_teste() -> str:
    url = os.environ.get("DATABASE_URL_TESTE", "")
    if not url:
        pytest.fail(
            "DATABASE_URL_TESTE ausente: defina a URL administrativa "
            "postgresql+psycopg://... do servidor de testes.",
            pytrace=False,
        )
    return url


@pytest.fixture(scope="session")
def url_banco_teste(url_admin_teste: str) -> Iterator[str]:
    with _banco_efemero(url_admin_teste) as url:
        yield url


@pytest.fixture
def banco_limpo(url_admin_teste: str) -> Iterator[str]:
    with _banco_efemero(url_admin_teste) as url:
        yield url


@pytest.fixture
def config_alembic() -> Callable[[str], object]:
    from alembic.config import Config

    def _montar(url: str) -> Config:
        cfg = Config(str(RAIZ_BACKEND / "alembic.ini"))
        cfg.set_main_option("script_location", str(RAIZ_BACKEND / "alembic"))
        cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
        return cfg

    return _montar


@pytest.fixture
def banco_migrado(banco_limpo: str, config_alembic) -> str:
    from alembic import command

    command.upgrade(config_alembic(banco_limpo), "head")
    return banco_limpo
