import errno
import json
import time
import uuid

import pytest
import redis
from celery.exceptions import SoftTimeLimitExceeded
from redis.backoff import NoBackoff
from redis.retry import Retry
from sqlalchemy import text

from app.pipeline.armazenamento import ErroArmazenamento
from app.pipeline.erros import MENSAGENS, ErroPipeline
from app.pipeline.executor import ExecutorPipeline
from testes.pipeline.auxiliares import montar_registro

CAMINHO = "/dados/segredo/arquivo.mp4"
SQL = "SELECT * FROM usuarios"
SENHA = "hunter2"
RASTREIO = "Traceback"
SENSIVEIS = (CAMINHO, SQL, SENHA, RASTREIO)
TEXTO = f"falha em {CAMINHO}\n{SQL} com senha {SENHA}\n{RASTREIO} (most recent call last):"

CASOS = [
    pytest.param(lambda: RuntimeError(TEXTO), "INTERNO", id="runtime"),
    pytest.param(lambda: ValueError(TEXTO), "INTERNO", id="valor"),
    pytest.param(lambda: OSError(errno.ENOSPC, TEXTO, CAMINHO), "ARMAZENAMENTO", id="oserror"),
    pytest.param(lambda: ErroArmazenamento(TEXTO), "ARMAZENAMENTO", id="armazenamento"),
    pytest.param(lambda: TimeoutError(TEXTO), "TEMPO_ESGOTADO", id="timeout"),
    pytest.param(lambda: SoftTimeLimitExceeded(TEXTO), "TEMPO_ESGOTADO", id="limite_celery"),
    pytest.param(
        lambda: ErroPipeline("ENTRADA_INVALIDA", TEXTO), "ENTRADA_INVALIDA", id="pipeline"
    ),
]


def _saidas_publicas(cenario, captura, erro) -> dict[str, str]:
    (linha,) = cenario.linhas()
    eventos = captura.aguardar(3)
    assert any(e["tipo"] == "erro" for e in eventos), "evento de erro não publicado"
    return {
        "str(erro)": str(erro),
        "erro_amigavel": cenario.banco.analise(cenario.analise_id)["erro_amigavel"] or "",
        "metricas": json.dumps(linha["metricas"], default=str),
        "artefatos": json.dumps(linha["artefatos"], default=str),
        "eventos": json.dumps(eventos, default=str),
    }


def _sem_vazamento(saidas: dict[str, str], proibidos) -> None:
    for onde, conteudo in saidas.items():
        for fragmento in proibidos:
            assert fragmento not in conteudo, f"{fragmento!r} vazou em {onde}"


class TestSemVazamento:
    @pytest.mark.parametrize(("fabrica", "codigo"), CASOS)
    def test_texto_da_excecao_fica_so_no_log(
        self, cenario, capturar_eventos, texto_logs, fabrica, codigo
    ):
        captura = capturar_eventos()
        cenario.etapa.falhas["p2"] = fabrica

        with pytest.raises(ErroPipeline) as capturado:
            cenario.executar()

        erro = capturado.value
        assert erro.codigo == codigo
        assert str(erro) == MENSAGENS[codigo]
        assert erro.__cause__ is not None
        saidas = _saidas_publicas(cenario, captura, erro)
        assert saidas["erro_amigavel"] == MENSAGENS[codigo]
        (linha,) = cenario.linhas()
        assert linha["status"] == "falhou"
        assert linha["metricas"]["erro_codigo"] == codigo
        _sem_vazamento(saidas, SENSIVEIS)
        assert SENHA in texto_logs()
        assert CAMINHO in texto_logs()

    def test_erro_de_banco_real_nao_vaza_sql_nem_valores(
        self, cenario, motor_auth, capturar_eventos, texto_logs
    ):
        captura = capturar_eventos()
        ids = (uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
        capturado_no_passo = []

        def violar_constraint(ctx):
            try:
                with motor_auth.begin() as con:
                    con.execute(
                        text(
                            "INSERT INTO analises (id, user_id, video_id, parametros) "
                            "VALUES (:a, :u, :v, CAST('{\"hunter2\": 1}' AS jsonb))"
                        ),
                        {"a": ids[0], "u": ids[1], "v": ids[2]},
                    )
            except Exception as erro:
                capturado_no_passo.append(str(erro))
                raise

        cenario.etapa.comportamentos["p2"] = violar_constraint

        with pytest.raises(ErroPipeline) as capturado:
            cenario.executar()

        erro = capturado.value
        assert capturado_no_passo, "o banco deveria ter recusado a inserção"
        assert "INSERT INTO analises" in capturado_no_passo[0]
        assert erro.codigo == "INTERNO"
        assert str(erro) == MENSAGENS["INTERNO"]
        saidas = _saidas_publicas(cenario, captura, erro)
        proibidos = ("INSERT INTO", "[SQL:", "analises", SENHA, *map(str, ids))
        _sem_vazamento(saidas, proibidos)
        assert "INSERT INTO analises" in texto_logs()

    def test_falha_de_gravacao_por_disco_nao_vaza_caminho(
        self, cenario, capturar_eventos, texto_logs
    ):
        captura = capturar_eventos()

        def disco_cheio(ctx):
            with ctx.gravacao_atomica("alfa_p1.json") as gravacao:
                gravacao.caminho.write_bytes(b"{")
                raise OSError(errno.ENOSPC, "No space left on device", CAMINHO)

        cenario.etapa.comportamentos["p1"] = disco_cheio

        with pytest.raises(ErroPipeline) as capturado:
            cenario.executar()

        erro = capturado.value
        assert erro.codigo == "ARMAZENAMENTO"
        saidas = _saidas_publicas(cenario, captura, erro)
        _sem_vazamento(saidas, (CAMINHO, "No space left", str(cenario.raiz)))
        assert CAMINHO in texto_logs()


class TestRedisForaDoAr:
    @pytest.fixture
    def redis_morto(self):
        cliente = redis.Redis(
            port=1,
            socket_connect_timeout=0.2,
            socket_timeout=0.5,
            retry=Retry(NoBackoff(), 0),
        )
        yield cliente
        cliente.close()

    def test_pubsub_indisponivel_nao_derruba_etapa_sem_gpu(
        self,
        dono,
        registrar_analise,
        etapa_de_teste,
        fabrica_sessao,
        armazenamento,
        banco_pipeline,
        redis_morto,
    ):
        etapa = etapa_de_teste("alfa", parametros=("semente",))
        analise_id, _ = registrar_analise(dono)
        executor = ExecutorPipeline(
            fabrica_sessao, redis_morto, armazenamento, montar_registro(etapa), trava_espera_s=1.0
        )
        inicio = time.monotonic()

        resultado = executor.executar(analise_id, dono, "alfa")

        assert resultado.status == "concluida"
        assert time.monotonic() - inicio < 30
        (linha,) = banco_pipeline.execucoes(analise_id, "alfa")
        assert linha["status"] == "concluida"
        assert etapa.contagens() == {"p1": 1, "p2": 1, "p3": 1}

    def test_trava_gpu_com_redis_fora_do_ar_falha_fechada(
        self,
        dono,
        registrar_analise,
        etapa_de_teste,
        fabrica_sessao,
        armazenamento,
        banco_pipeline,
        redis_morto,
    ):
        etapa = etapa_de_teste("alfa", usa_gpu=True, fila="gpu")
        analise_id, _ = registrar_analise(dono)
        executor = ExecutorPipeline(
            fabrica_sessao, redis_morto, armazenamento, montar_registro(etapa), trava_espera_s=30.0
        )
        inicio = time.monotonic()

        with pytest.raises(ErroPipeline) as capturado:
            executor.executar(analise_id, dono, "alfa")

        assert capturado.value.codigo == "GPU_INDISPONIVEL"
        assert time.monotonic() - inicio < 15
        assert etapa.contagens() == {"p1": 0, "p2": 0, "p3": 0}
        (linha,) = banco_pipeline.execucoes(analise_id, "alfa")
        assert linha["status"] == "falhou"
