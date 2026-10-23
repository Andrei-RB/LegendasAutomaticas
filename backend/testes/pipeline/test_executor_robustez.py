import json
import uuid

import pytest
from celery.exceptions import Retry
from sqlalchemy import text

from app.pipeline import tarefas
from app.pipeline.erros import MENSAGENS, ErroPipeline
from app.pipeline.executor import Etapa, Passo, ResultadoEtapa
from app.pipeline.hashing import calcular_hash_entrada
from app.pipeline.registro import registro_padrao
from testes.pipeline.conftest import Cenario


def _segunda_analise(cenario: Cenario, parametros: dict) -> uuid.UUID:
    """Nova análise do mesmo usuário e do mesmo vídeo."""
    analise_id = uuid.uuid4()
    with cenario.banco.motor.begin() as con:
        con.execute(
            text(
                "INSERT INTO analises (id, user_id, video_id, parametros) "
                "VALUES (:a, :u, :v, CAST(:p AS jsonb))"
            ),
            {
                "a": analise_id,
                "u": cenario.user_id,
                "v": cenario.video_id,
                "p": json.dumps(parametros),
            },
        )
    return analise_id


class TestEscopoDosArtefatos:
    def test_analises_do_mesmo_video_nao_compartilham_arquivos(self, cenario):
        outra = _segunda_analise(cenario, {"semente": 2})

        cenario.executar()
        cenario.executor.executar(outra, cenario.user_id, "alfa")

        pasta_a = cenario.caminho("alfa_p1.json").parent
        pasta_b = pasta_a.parent / str(outra)
        assert pasta_a != pasta_b
        assert json.loads((pasta_a / "alfa_p1.json").read_bytes())["parametros"] == {"semente": 1}
        assert json.loads((pasta_b / "alfa_p1.json").read_bytes())["parametros"] == {"semente": 2}

    def test_execucao_da_outra_analise_nao_invalida_a_primeira(self, cenario):
        outra = _segunda_analise(cenario, {"semente": 2})
        cenario.executar()
        cenario.executor.executar(outra, cenario.user_id, "alfa")

        repetida = cenario.executar()

        assert repetida.status == "pulada"
        assert cenario.etapa.contagens() == {"p1": 2, "p2": 2, "p3": 2}

    def test_saida_antiga_nao_declarada_como_nova_e_recusada(self, cenario):
        pasta = cenario.caminho("alfa_p1.json").parent
        pasta.mkdir(parents=True)
        (pasta / "alfa_p1.json").write_bytes(b'{"sobra": true}')
        cenario.etapa.comportamentos["p1"] = lambda ctx: None

        with pytest.raises(ErroPipeline) as capturado:
            cenario.executar()

        assert capturado.value.codigo == "INTERNO"
        (linha,) = cenario.linhas()
        assert linha["status"] == "falhou"
        assert linha["artefatos"] == {}


class TestFencing:
    def test_execucao_reivindicada_por_outro_worker_nao_e_sobrescrita(self, cenario):
        def reivindicada(ctx, passo):
            if passo == "p2":
                with cenario.banco.motor.begin() as con:
                    con.execute(
                        text(
                            "UPDATE execucoes_etapa SET iniciado_em = now() + interval '1 hour' "
                            "WHERE analise_id = :a"
                        ),
                        {"a": cenario.analise_id},
                    )

        cenario.etapa.gancho = reivindicada

        with pytest.raises(ErroPipeline):
            cenario.executar()

        (linha,) = cenario.linhas()
        assert linha["status"] == "executando"
        assert set(linha["artefatos"]) == {"p1"}
        assert cenario.banco.analise(cenario.analise_id)["status"] != "falhou"


class TestFalhasForaDoPasso:
    def test_interrupcao_do_processo_marca_a_execucao_como_falhou(self, cenario):
        cenario.etapa.falhas["p2"] = KeyboardInterrupt()

        with pytest.raises(KeyboardInterrupt):
            cenario.executar()

        (linha,) = cenario.linhas()
        assert linha["status"] == "falhou"

    def test_entrada_ausente_marca_a_analise_e_emite_erro(self, montar_cenario, capturar_eventos):
        cenario = montar_cenario(entradas=("base",))
        captura = capturar_eventos()

        with pytest.raises(ErroPipeline) as capturado:
            cenario.executar()

        assert capturado.value.codigo == "ENTRADA_AUSENTE"
        analise = cenario.banco.analise(cenario.analise_id)
        assert analise["status"] == "falhou"
        assert analise["erro_amigavel"] == MENSAGENS["ENTRADA_AUSENTE"]
        eventos = captura.aguardar(1)
        assert [e["tipo"] for e in eventos] == ["erro"]
        assert eventos[0]["codigo"] == "ENTRADA_AUSENTE"

    def test_erro_nao_residual_apos_retomada_bem_sucedida(self, cenario):
        cenario.etapa.falhas["p2"] = RuntimeError("falha")
        with pytest.raises(ErroPipeline):
            cenario.executar()
        cenario.etapa.falhas.clear()

        cenario.executar()

        (linha,) = cenario.linhas()
        assert linha["status"] == "concluida"
        assert "erro_codigo" not in linha["metricas"]


class TestLimiteDaEtapa:
    def test_limite_acima_do_visibility_timeout_e_recusado(self):
        passo = Passo(nome="p1", saidas=("a.json",), executar=lambda ctx: None)
        with pytest.raises(ValueError):
            Etapa(nome="longa", versao=1, fila="cpu", passos=(passo,), limite_s=7200)


class TestRetomadaPorReentrega:
    def test_lease_vigente_informa_o_tempo_restante(self, montar_cenario):
        cenario = montar_cenario(limite_s=10, opcoes_executor={"lease_extra_s": 50})
        cenario.banco.inserir_execucao(
            cenario.analise_id,
            cenario.user_id,
            "alfa",
            "executando",
            hash_entrada=calcular_hash_entrada("alfa", 1, {}, {"semente": 1}),
            iniciado_ha_s=20,
        )

        resultado = cenario.executar()

        assert resultado.status == "em_execucao"
        assert 30 < resultado.lease_restante_s <= 40


class TestTarefaReentregue:
    ANALISE = uuid.UUID("44444444-4444-4444-8444-444444444444")
    USUARIO = uuid.UUID("11111111-1111-4111-8111-111111111111")

    @staticmethod
    def _executor(resultado=None, erro=None):
        class Falso:
            def executar(self, *_):
                if erro is not None:
                    raise erro
                return resultado

        return Falso()

    def test_em_execucao_reagenda_a_tarefa_ate_o_lease_vencer(self, monkeypatch):
        resultado = ResultadoEtapa("em_execucao", "a" * 64, (), (), lease_restante_s=120.4)
        monkeypatch.setattr(tarefas, "obter_executor", lambda: self._executor(resultado))
        agendados = []

        def _retry(*, countdown, **_):
            agendados.append(countdown)
            return Retry("agendada", None)

        monkeypatch.setattr(tarefas.executar_etapa_task, "retry", _retry, raising=False)

        with pytest.raises(Retry):
            tarefas.executar_etapa_task(str(self.ANALISE), str(self.USUARIO), "exemplo")

        assert len(agendados) == 1
        assert 5 <= agendados[0] <= 60

    def test_excecao_inesperada_vira_falha_interna_sem_vazar_detalhe(self, monkeypatch):
        erro = RuntimeError("SELECT senha FROM usuarios /dados/u/v/x.mp4")
        monkeypatch.setattr(tarefas, "obter_executor", lambda: self._executor(erro=erro))

        resposta = tarefas.executar_etapa_task(str(self.ANALISE), str(self.USUARIO), "exemplo")

        assert resposta == {"status": "falhou", "codigo": "INTERNO"}


def test_contem_etapa_nao_hashable_devolve_falso():
    assert ([] in registro_padrao) is False
    assert ({} in registro_padrao) is False
