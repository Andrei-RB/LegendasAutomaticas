import json
import socket
import threading
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import text

from testes.pipeline.auxiliares import (
    Captura,
    Chamadas,
    ClienteRedisAssincronoInterruptivel,
    ClienteRedisInterruptivel,
    EtapaDeTeste,
    Servidor,
    esperar_ate,
    montar_registro,
)


class BancoPipeline:
    """Consultas e escritas diretas nas tabelas do pipeline, por SQL, com o motor de testes."""

    def __init__(self, motor: Any) -> None:
        self.motor = motor

    def execucoes(self, analise_id: uuid.UUID, etapa: str | None = None) -> list[dict[str, Any]]:
        consulta = "SELECT * FROM execucoes_etapa WHERE analise_id = :a"
        parametros: dict[str, Any] = {"a": analise_id}
        if etapa is not None:
            consulta += " AND etapa = :e"
            parametros["e"] = etapa
        with self.motor.connect() as con:
            linhas = con.execute(text(consulta + " ORDER BY criado_em, id"), parametros)
            return [dict(linha._mapping) for linha in linhas]

    def analise(self, analise_id: uuid.UUID) -> dict[str, Any]:
        with self.motor.connect() as con:
            linha = con.execute(text("SELECT * FROM analises WHERE id = :a"), {"a": analise_id})
            return dict(linha.one()._mapping)

    def definir_parametros(self, analise_id: uuid.UUID, parametros: dict[str, Any]) -> None:
        with self.motor.begin() as con:
            con.execute(
                text("UPDATE analises SET parametros = CAST(:p AS jsonb) WHERE id = :a"),
                {"p": json.dumps(parametros), "a": analise_id},
            )

    def definir_analise(self, analise_id: uuid.UUID, **campos: Any) -> None:
        atribuicoes = ", ".join(f"{nome} = :{nome}" for nome in campos)
        with self.motor.begin() as con:
            con.execute(
                text(f"UPDATE analises SET {atribuicoes} WHERE id = :a"),  # noqa: S608
                {**campos, "a": analise_id},
            )

    def inserir_execucao(
        self,
        analise_id: uuid.UUID,
        user_id: uuid.UUID,
        etapa: str,
        status: str,
        *,
        hash_entrada: str | None = None,
        iniciado_ha_s: float | None = None,
        criado_em: datetime | None = None,
        artefatos: dict[str, Any] | None = None,
        metricas: dict[str, Any] | None = None,
    ) -> str:
        hash_final = hash_entrada or uuid.uuid4().hex + uuid.uuid4().hex
        with self.motor.begin() as con:
            con.execute(
                text(
                    "INSERT INTO execucoes_etapa (user_id, analise_id, etapa, hash_entrada, "
                    "status, artefatos, metricas, iniciado_em, criado_em) VALUES (:u, :a, :e, "
                    ":h, :s, CAST(:art AS jsonb), CAST(:met AS jsonb), "
                    "CASE WHEN CAST(:ini AS float) IS NULL THEN NULL "
                    "ELSE now() - CAST(:ini AS float) * interval '1 second' END, "
                    "COALESCE(CAST(:c AS timestamptz), now()))"
                ),
                {
                    "u": user_id,
                    "a": analise_id,
                    "e": etapa,
                    "h": hash_final,
                    "s": status,
                    "art": json.dumps(artefatos or {}),
                    "met": json.dumps(metricas or {}),
                    "ini": iniciado_ha_s,
                    "c": criado_em,
                },
            )
        return hash_final

    def transacoes_abertas(self) -> int:
        """Sessões deste banco paradas dentro de uma transação, exceto a própria consulta."""
        with self.motor.connect() as con:
            return int(
                con.execute(
                    text(
                        "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
                        "AND state LIKE 'idle in transaction%' AND pid <> pg_backend_pid()"
                    )
                ).scalar_one()
            )


@pytest.fixture
def banco_pipeline(motor_auth) -> BancoPipeline:
    return BancoPipeline(motor_auth)


@pytest.fixture
def raiz_dados(tmp_path: Path) -> Path:
    return tmp_path / "dados"


@pytest.fixture
def armazenamento(raiz_dados: Path):
    from app.pipeline.armazenamento import ArmazenamentoLocal

    return ArmazenamentoLocal(raiz_dados)


@pytest.fixture
def usuario_a(criar_usuario):
    return criar_usuario("a@exemplo.com", "usuario_a")


@pytest.fixture
def usuario_b(criar_usuario):
    return criar_usuario("b@exemplo.com", "usuario_b")


@pytest.fixture
def dono(usuario_a) -> uuid.UUID:
    return uuid.UUID(usuario_a.id)


@pytest.fixture
def outro_dono(usuario_b) -> uuid.UUID:
    return uuid.UUID(usuario_b.id)


@pytest.fixture
def registrar_analise(ambiente) -> Callable[..., tuple[uuid.UUID, uuid.UUID]]:
    """Insere `videos` e `analises` por SQL e devolve `(analise_id, video_id)`."""

    def _registrar(
        user_id: uuid.UUID | str, parametros: dict[str, Any] | None = None
    ) -> tuple[uuid.UUID, uuid.UUID]:
        dono_id = uuid.UUID(str(user_id))
        video_id, analise_id = uuid.uuid4(), uuid.uuid4()
        with ambiente.motor.begin() as con:
            con.execute(
                text(
                    "INSERT INTO videos (id, user_id, origem, caminho_original) "
                    "VALUES (:v, :u, 'upload', '/uploads/x.mp4')"
                ),
                {"v": video_id, "u": dono_id},
            )
            con.execute(
                text(
                    "INSERT INTO analises (id, user_id, video_id, parametros) "
                    "VALUES (:a, :u, :v, CAST(:p AS jsonb))"
                ),
                {
                    "a": analise_id,
                    "u": dono_id,
                    "v": video_id,
                    "p": json.dumps({"semente": 1} if parametros is None else parametros),
                },
            )
        return analise_id, video_id

    return _registrar


@pytest.fixture
def fabrica_sessao(motor_auth):
    from sqlalchemy.orm import sessionmaker

    return sessionmaker(bind=motor_auth, expire_on_commit=False)


@pytest.fixture
def construir_executor(fabrica_sessao, redis_teste, armazenamento) -> Callable[..., Any]:
    def _construir(registro: Any, **opcoes: Any) -> Any:
        from app.pipeline.executor import ExecutorPipeline

        padrao: dict[str, Any] = {"trava_espera_s": 20.0, "trava_ttl_ms": 10_000}
        return ExecutorPipeline(
            fabrica_sessao, redis_teste, armazenamento, registro, **{**padrao, **opcoes}
        )

    return _construir


@pytest.fixture
def etapa_de_teste() -> Callable[..., EtapaDeTeste]:
    """Fábrica de etapas sintéticas com contadores thread-safe e falhas programáveis."""

    def _criar(nome: str = "alfa", **opcoes: Any) -> EtapaDeTeste:
        return EtapaDeTeste(nome, **opcoes)

    return _criar


@dataclass
class Cenario:
    user_id: uuid.UUID
    analise_id: uuid.UUID
    video_id: uuid.UUID
    etapa: EtapaDeTeste
    executor: Any
    banco: BancoPipeline
    raiz: Path

    def executar(self, etapa: str | None = None) -> Any:
        return self.executor.executar(
            self.analise_id, self.user_id, etapa if etapa is not None else self.etapa.nome
        )

    def linhas(self, etapa: str | None = None) -> list[dict[str, Any]]:
        return self.banco.execucoes(
            self.analise_id, etapa if etapa is not None else self.etapa.nome
        )

    def caminho(self, nome: str) -> Path:
        return self.raiz / str(self.user_id) / str(self.video_id) / str(self.analise_id) / nome

    def diretorio(self) -> Path:
        return self.raiz / str(self.user_id) / str(self.video_id)


@pytest.fixture
def montar_cenario(
    dono, registrar_analise, etapa_de_teste, construir_executor, banco_pipeline, raiz_dados
) -> Callable[..., Cenario]:
    """Monta análise, etapa sintética e executor; `opcoes_executor` vai ao ExecutorPipeline."""

    def _montar(
        *,
        parametros: dict[str, Any] | None = None,
        opcoes_executor: dict[str, Any] | None = None,
        **opcoes_etapa: Any,
    ) -> Cenario:
        opcoes_etapa.setdefault("parametros", ("semente",))
        etapa = etapa_de_teste(**opcoes_etapa)
        analise_id, video_id = registrar_analise(dono, parametros)
        executor = construir_executor(montar_registro(etapa), **(opcoes_executor or {}))
        return Cenario(dono, analise_id, video_id, etapa, executor, banco_pipeline, raiz_dados)

    return _montar


@pytest.fixture
def cenario(montar_cenario) -> Cenario:
    return montar_cenario()


@pytest.fixture
def novas_chamadas() -> Callable[[], Chamadas]:
    return Chamadas


@pytest.fixture
def capturar_eventos(url_redis_teste: str) -> Iterator[Callable[[], Captura]]:
    criadas: list[Captura] = []

    def _criar() -> Captura:
        captura = Captura(url_redis_teste)
        criadas.append(captura)
        return captura

    yield _criar
    for captura in criadas:
        captura.encerrar()


@pytest.fixture
def servidor_http(ambiente, url_redis_teste: str, monkeypatch) -> Iterator[Servidor]:
    """Uvicorn real em thread, com os overrides do `ambiente` e Redis com falha injetável."""
    import uvicorn

    from app.nucleo.config import settings
    from app.nucleo.dependencias import obter_fabrica_redis_assincrono, obter_redis

    monkeypatch.setattr(settings, "SSE_HEARTBEAT_S", 30.0)
    interruptor = threading.Event()
    sincrono = ClienteRedisInterruptivel.from_url(url_redis_teste)
    sincrono.interruptor = interruptor

    def _fabrica_assincrona() -> ClienteRedisAssincronoInterruptivel:
        cliente = ClienteRedisAssincronoInterruptivel.from_url(url_redis_teste)
        cliente.interruptor = interruptor
        return cliente

    ambiente.app.dependency_overrides[obter_redis] = lambda: sincrono
    ambiente.app.dependency_overrides[obter_fabrica_redis_assincrono] = lambda: _fabrica_assincrona

    soquete = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    soquete.bind(("127.0.0.1", 0))
    porta = soquete.getsockname()[1]
    config = uvicorn.Config(
        ambiente.app,
        log_level="warning",
        lifespan="off",
        access_log=False,
        ws="none",
        timeout_graceful_shutdown=2,
    )
    servidor = uvicorn.Server(config)
    fio = threading.Thread(target=servidor.run, kwargs={"sockets": [soquete]}, daemon=True)
    fio.start()
    assert esperar_ate(lambda: servidor.started, timeout=15), "uvicorn não iniciou"
    api = Servidor(porta, interruptor)
    try:
        yield api
    finally:
        interruptor.clear()
        api.fechar_leitores()
        servidor.should_exit = True
        fio.join(timeout=10)
        if fio.is_alive():
            servidor.force_exit = True
            fio.join(timeout=5)
        soquete.close()
        sincrono.close()


@pytest.fixture
def publicar(redis_teste) -> Callable[..., None]:
    """Publica no canal do pipeline um evento (modelo ou texto bruto)."""

    def _publicar(user_id: uuid.UUID, analise_id: uuid.UUID, evento: Any, canal: str | None = None):
        from app.pipeline.eventos import canal as nome_canal

        corpo = evento if isinstance(evento, str | bytes) else evento.to_json()
        redis_teste.publish(canal or nome_canal(user_id, analise_id), corpo)

    return _publicar


@pytest.fixture
def analise_a(dono, registrar_analise) -> uuid.UUID:
    return registrar_analise(dono)[0]


@pytest.fixture
def analise_b(outro_dono, registrar_analise) -> uuid.UUID:
    return registrar_analise(outro_dono)[0]


@pytest.fixture
def token_a(servidor_http, usuario_a) -> str:
    return servidor_http.login(usuario_a)


@pytest.fixture
def token_b(servidor_http, usuario_b) -> str:
    return servidor_http.login(usuario_b)
