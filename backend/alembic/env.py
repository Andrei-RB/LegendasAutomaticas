import app.modelos  # noqa: F401  (registra os modelos nos metadados)
from alembic import context
from app.nucleo.banco import Base, criar_motor
from app.nucleo.config import settings

config = context.config
target_metadata = Base.metadata


def _url() -> str:
    return config.get_main_option("sqlalchemy.url") or settings.DATABASE_URL.get_secret_value()


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        compare_server_default=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    motor = criar_motor(_url())
    try:
        with motor.connect() as conexao:
            context.configure(
                connection=conexao,
                target_metadata=target_metadata,
                compare_type=True,
                compare_server_default=True,
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        motor.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
