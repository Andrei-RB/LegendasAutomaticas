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
JWT_SECRET_TESTE = "segredo-jwt-apenas-para-testes-" + "0123456789abcdef" * 3
os.environ["JWT_SECRET"] = JWT_SECRET_TESTE
ORIGEM_PERMITIDA = "http://localhost:8501"
SENHA_PADRAO = "senha-padrao-de-teste-1"

import logging  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from typing import Any  # noqa: E402

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


def _montar_config_alembic(url: str):
    from alembic.config import Config

    cfg = Config(str(RAIZ_BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(RAIZ_BACKEND / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return cfg


@pytest.fixture
def config_alembic() -> Callable[[str], object]:
    return _montar_config_alembic


@pytest.fixture
def banco_migrado(banco_limpo: str, config_alembic) -> str:
    from alembic import command

    command.upgrade(config_alembic(banco_limpo), "head")
    return banco_limpo


@pytest.fixture(scope="session")
def url_redis_teste() -> str:
    url = os.environ.get("REDIS_URL_TESTE", "")
    if not url:
        pytest.fail(
            "REDIS_URL_TESTE ausente: defina a URL de um Redis efêmero de testes (redis://.../15).",
            pytrace=False,
        )
    return url


@pytest.fixture
def redis_teste(url_redis_teste: str) -> Iterator[Any]:
    import redis

    cliente_redis = redis.Redis.from_url(url_redis_teste)
    cliente_redis.flushdb()
    yield cliente_redis
    cliente_redis.flushdb()
    cliente_redis.close()


@pytest.fixture(scope="session")
def motor_auth(url_banco_teste: str) -> Iterator[Any]:
    from sqlalchemy import create_engine

    from alembic import command

    command.upgrade(_montar_config_alembic(url_banco_teste), "head")
    motor = create_engine(url_banco_teste)
    yield motor
    motor.dispose()


@dataclass
class Ambiente:
    app: Any
    motor: Any
    redis: Any


@pytest.fixture
def ambiente(motor_auth, redis_teste, monkeypatch) -> Iterator[Ambiente]:
    """App real ligada ao PostgreSQL e ao Redis de testes, com tabela de usuários limpa."""
    from sqlalchemy import text
    from sqlalchemy.orm import sessionmaker

    from app.main import app
    from app.nucleo.config_auth import config_auth as settings
    from app.nucleo.dependencias import obter_fabrica_sessao, obter_redis, obter_sessao

    monkeypatch.setattr(settings, "COOKIE_SECURE", False)
    monkeypatch.setattr(settings, "PERMITIR_CADASTRO", False)
    with motor_auth.begin() as con:
        con.execute(text("TRUNCATE usuarios CASCADE"))

    fabrica = sessionmaker(bind=motor_auth, expire_on_commit=False)

    def _sessao():
        with fabrica() as sessao:
            yield sessao

    app.dependency_overrides[obter_sessao] = _sessao
    app.dependency_overrides[obter_fabrica_sessao] = lambda: fabrica
    app.dependency_overrides[obter_redis] = lambda: redis_teste
    yield Ambiente(app=app, motor=motor_auth, redis=redis_teste)
    app.dependency_overrides.clear()


@pytest.fixture
def novo_cliente(ambiente: Ambiente):
    """Fábrica de clientes HTTP com jar de cookies próprio; `origem=None` não envia Origin."""
    from fastapi.testclient import TestClient

    criados = []

    def _criar(origem: str | None = ORIGEM_PERMITIDA, **cabecalhos: str) -> TestClient:
        enviados = dict(cabecalhos)
        if origem is not None:
            enviados["Origin"] = origem
        cliente_http = TestClient(ambiente.app, headers=enviados)
        criados.append(cliente_http)
        return cliente_http

    yield _criar
    for cliente_http in criados:
        cliente_http.close()


@dataclass
class UsuarioTeste:
    cliente: Any
    id: str
    email: str
    senha: str
    nome_usuario: str


@pytest.fixture
def criar_usuario(ambiente: Ambiente, novo_cliente):
    """Cadastra e autentica um usuário; libera o cadastro apenas durante a chamada."""
    from app.nucleo.config_auth import config_auth as settings

    def _criar(
        email: str = "ana@exemplo.com",
        nome_usuario: str = "ana",
        senha: str = SENHA_PADRAO,
    ) -> UsuarioTeste:
        cliente_http = novo_cliente()
        anterior = settings.PERMITIR_CADASTRO
        settings.PERMITIR_CADASTRO = True
        try:
            cadastro = cliente_http.post(
                "/api/v1/auth/cadastro",
                json={"email": email, "senha": senha, "nome_usuario": nome_usuario},
            )
        finally:
            settings.PERMITIR_CADASTRO = anterior
        assert cadastro.status_code == 201, cadastro.text
        entrada = cliente_http.post("/api/v1/auth/login", json={"email": email, "senha": senha})
        assert entrada.status_code == 200, entrada.text
        return UsuarioTeste(
            cliente=cliente_http,
            id=cadastro.json()["id"],
            email=email,
            senha=senha,
            nome_usuario=nome_usuario,
        )

    return _criar


@pytest.fixture
def usuario_logado(criar_usuario) -> UsuarioTeste:
    return criar_usuario()


@pytest.fixture
def cliente_logado(usuario_logado: UsuarioTeste):
    return usuario_logado.cliente


@pytest.fixture
def registrar_video(ambiente: Ambiente):
    """Insere em `videos` a linha do job, como o upload faz."""
    from sqlalchemy import text

    def _registrar(user_id: str, job_id: str) -> None:
        with ambiente.motor.begin() as con:
            con.execute(
                text(
                    "INSERT INTO videos (id, user_id, origem, caminho_original) "
                    "VALUES (:i, :u, 'upload', '/uploads/x.mp4')"
                ),
                {"i": job_id, "u": user_id},
            )

    return _registrar


@pytest.fixture
def texto_logs(caplog):
    """Devolve uma função que reúne os logs da aplicação (memória e arquivo)."""
    from app.nucleo.config import settings

    registro = logging.getLogger("app")
    registro.addHandler(caplog.handler)
    caplog.set_level(logging.DEBUG, logger="app")

    def _ler() -> str:
        caminho = Path(settings.LOG_DIR) / "app.log"
        arquivo = caminho.read_text(encoding="utf-8") if caminho.exists() else ""
        return caplog.text + arquivo

    yield _ler
    registro.removeHandler(caplog.handler)
