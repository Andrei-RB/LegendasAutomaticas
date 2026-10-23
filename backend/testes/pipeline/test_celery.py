import json
import uuid
from types import SimpleNamespace

import pytest

from app.pipeline import tarefas
from app.pipeline.erros import MENSAGENS, ErroPipeline
from app.pipeline.executor import ResultadoEtapa
from app.pipeline.registro import registro_padrao
from app.workers.celery_app import celery_app
from app.workers.tasks import process_video_task

NOME_TAREFA = "pipeline.executar_etapa"
USUARIO = uuid.UUID("11111111-1111-4111-8111-111111111111")
ANALISE = uuid.UUID("44444444-4444-4444-8444-444444444444")


class ExecutorFalso:
    """Executor simulado: registra as chamadas e devolve um resultado ou levanta um erro."""

    def __init__(self, resultado=None, erro=None):
        self.resultado = resultado
        self.erro = erro
        self.chamadas = []

    def executar(self, analise_id, user_id, etapa):
        self.chamadas.append((analise_id, user_id, etapa))
        if self.erro is not None:
            raise self.erro
        return self.resultado


@pytest.fixture
def instalar_executor(monkeypatch):
    """Substitui `obter_executor` e conta quantas vezes foi pedido."""
    pedidos = []

    def _instalar(executor):
        def _obter():
            pedidos.append(1)
            return executor

        monkeypatch.setattr(tarefas, "obter_executor", _obter)
        return pedidos

    return _instalar


def _resultado(status="concluida", hash_entrada="a" * 64):
    return ResultadoEtapa(
        status=status,
        hash_entrada=hash_entrada,
        passos_executados=("p1",),
        passos_reaproveitados=(),
    )


def _rota(nome, kwargs):
    return celery_app.amqp.router.route({}, nome, (), kwargs)


# configuração do aplicativo Celery


def test_include_contem_tarefas_do_pipeline_e_as_antigas():
    assert "app.pipeline.tarefas" in celery_app.conf.include
    assert "app.workers.tasks" in celery_app.conf.include


def test_filas_declaradas_sao_exatamente_as_previstas():
    nomes = [fila.name for fila in celery_app.conf.task_queues]

    assert sorted(nomes) == ["ai", "celery", "cpu", "gpu", "render"]


def test_visibility_timeout_cobre_etapas_longas():
    assert celery_app.conf.broker_transport_options["visibility_timeout"] >= 7200


def test_tarefa_registrada_com_confirmacao_tardia_e_rejeicao_se_worker_morre():
    tarefa = celery_app.tasks[NOME_TAREFA]

    assert tarefa.name == tarefas.executar_etapa_task.name
    assert tarefa.name == NOME_TAREFA
    assert tarefa.acks_late is True
    assert tarefa.reject_on_worker_lost is True


@pytest.mark.parametrize(
    ("etapa", "fila"), [("exemplo", "cpu"), ("exemplo_gpu", "gpu")], ids=["cpu", "gpu"]
)
def test_roteador_envia_a_etapa_para_a_fila_do_registro(etapa, fila):
    kwargs = {"analise_id": str(ANALISE), "user_id": str(USUARIO), "etapa": etapa}

    rota = _rota(NOME_TAREFA, kwargs)

    assert registro_padrao.obter(etapa).fila == fila
    assert rota["queue"].name == fila


def test_roteador_nao_depende_de_argumentos_posicionais():
    rota = celery_app.amqp.router.route(
        {}, NOME_TAREFA, ("ignorado", "ignorado", "ignorado"), {"etapa": "exemplo_gpu"}
    )

    assert rota["queue"].name == "gpu"


def test_process_video_task_continua_na_fila_padrao():
    assert _rota("process_video_task", {})["queue"].name == "celery"


def test_process_video_task_continua_registrada():
    assert celery_app.tasks["process_video_task"].name == process_video_task.name


# enfileirar_etapa


@pytest.mark.parametrize(
    ("etapa", "fila"), [("exemplo", "cpu"), ("exemplo_gpu", "gpu")], ids=["cpu", "gpu"]
)
def test_enfileirar_etapa_envia_a_tarefa_na_fila_da_etapa(monkeypatch, etapa, fila):
    enviados = []

    def _send_task(nome, args=None, kwargs=None, **opcoes):
        enviados.append((nome, args, kwargs, opcoes))
        return SimpleNamespace(id="id-simulado")

    monkeypatch.setattr(celery_app, "send_task", _send_task)

    tarefas.enfileirar_etapa(ANALISE, USUARIO, etapa)

    assert len(enviados) == 1
    nome, args, kwargs, opcoes = enviados[0]
    assert nome == NOME_TAREFA
    assert not args
    assert kwargs == {"analise_id": str(ANALISE), "user_id": str(USUARIO), "etapa": etapa}
    json.dumps(kwargs)
    explicitas = {k: v for k, v in opcoes.items() if k in ("queue", "exchange", "routing_key")}
    assert celery_app.amqp.router.route(explicitas, nome, args or (), kwargs)["queue"].name == fila


# comportamento da tarefa com executor simulado


def test_sucesso_devolve_status_e_hash_e_repassa_uuids_ao_executor(instalar_executor):
    executor = ExecutorFalso(resultado=_resultado("concluida", "b" * 64))
    instalar_executor(executor)

    resposta = tarefas.executar_etapa_task(str(ANALISE), str(USUARIO), "exemplo")

    assert resposta["status"] == "concluida"
    assert resposta["hash_entrada"] == "b" * 64
    assert executor.chamadas == [(ANALISE, USUARIO, "exemplo")]
    assert isinstance(executor.chamadas[0][0], uuid.UUID)
    assert isinstance(executor.chamadas[0][1], uuid.UUID)
    json.dumps(resposta)


@pytest.mark.parametrize("status", ["concluida", "pulada"])
def test_status_do_executor_e_repassado(instalar_executor, status):
    instalar_executor(ExecutorFalso(resultado=_resultado(status)))

    resposta = tarefas.executar_etapa_task(str(ANALISE), str(USUARIO), "exemplo_gpu")

    assert resposta["status"] == status
    assert resposta["hash_entrada"] == "a" * 64


@pytest.mark.parametrize("codigo", ["ENTRADA_AUSENTE", "GPU_INDISPONIVEL", "ARMAZENAMENTO"])
def test_erro_do_executor_vira_resultado_falhou_sem_levantar(instalar_executor, codigo):
    causa = OSError("/dados/u/v/x.mp4: permissão negada")
    erro = ErroPipeline(codigo, "SELECT * FROM usuarios; Traceback (most recent call last)")
    erro.__cause__ = causa
    instalar_executor(ExecutorFalso(erro=erro))

    resposta = tarefas.executar_etapa_task(str(ANALISE), str(USUARIO), "exemplo")

    assert resposta["status"] == "falhou"
    assert resposta["codigo"] == codigo
    serializado = json.dumps(resposta)
    for proibido in ("Traceback", "SELECT", "/dados", "permissão negada"):
        assert proibido not in serializado


@pytest.mark.parametrize(
    "analise_id",
    ["nao-e-uuid", "", "../../etc/passwd", "123", str(ANALISE) + "x", "'; DROP TABLE analises;--"],
)
def test_analise_id_invalido_e_recusado_sem_tocar_o_executor(instalar_executor, analise_id):
    executor = ExecutorFalso(resultado=_resultado())
    pedidos = instalar_executor(executor)

    resposta = tarefas.executar_etapa_task(analise_id, str(USUARIO), "exemplo")

    assert resposta["status"] == "recusada"
    assert resposta["codigo"] == "ENTRADA_INVALIDA"
    assert pedidos == []
    assert executor.chamadas == []


@pytest.mark.parametrize("user_id", ["nao-e-uuid", "", "../x", str(USUARIO)[:-1]])
def test_user_id_invalido_e_recusado_sem_tocar_o_executor(instalar_executor, user_id):
    executor = ExecutorFalso(resultado=_resultado())
    pedidos = instalar_executor(executor)

    resposta = tarefas.executar_etapa_task(str(ANALISE), user_id, "exemplo")

    assert resposta["status"] == "recusada"
    assert resposta["codigo"] == "ENTRADA_INVALIDA"
    assert pedidos == []
    assert executor.chamadas == []


@pytest.mark.parametrize(
    "etapa",
    ["inexistente", "", "EXEMPLO", "exemplo; rm -rf /", "../exemplo", "x" * 5000, "exemplo\n"],
)
def test_etapa_fora_do_registro_e_recusada_sem_tocar_o_executor(instalar_executor, etapa):
    executor = ExecutorFalso(resultado=_resultado())
    pedidos = instalar_executor(executor)

    resposta = tarefas.executar_etapa_task(str(ANALISE), str(USUARIO), etapa)

    assert resposta["status"] == "recusada"
    assert resposta["codigo"] == "ETAPA_DESCONHECIDA"
    assert pedidos == []
    assert executor.chamadas == []
    assert resposta["codigo"] in MENSAGENS
    if etapa:
        assert etapa not in json.dumps(resposta)
