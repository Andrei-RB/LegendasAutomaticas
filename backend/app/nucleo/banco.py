from sqlalchemy import MetaData, create_engine
from sqlalchemy.engine import URL, Engine, make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# Nomes determinísticos de índices e restrições mantêm migrações e `alembic check` estáveis.
CONVENCAO_NOMES = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=CONVENCAO_NOMES)


def normalizar_url(url: str) -> URL:
    if not url.strip():
        raise ValueError("DATABASE_URL não definida")
    try:
        alvo = make_url(url.strip())
    except ArgumentError:
        raise ValueError("DATABASE_URL inválida") from None
    if alvo.get_backend_name() != "postgresql":
        raise ValueError("DATABASE_URL deve usar PostgreSQL")
    if alvo.drivername == "postgresql":
        alvo = alvo.set(drivername="postgresql+psycopg")
    return alvo


def criar_motor(url: str) -> Engine:
    alvo = normalizar_url(url)
    return create_engine(
        alvo,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        pool_recycle=1800,
        hide_parameters=True,
    )


def criar_fabrica_sessao(motor: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=motor, expire_on_commit=False)
