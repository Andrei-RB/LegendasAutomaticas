import threading
import time

import pytest

from app.pipeline.erros import ErroPipeline
from app.pipeline.hashing import calcular_hash_entrada
from testes.pipeline.auxiliares import montar_registro, sha256_de

PASSOS = ("p1", "p2", "p3")
TIMEOUT_FIO_S = 60


def _disparar(tarefas):
    """Executa as tarefas em threads liberadas ao mesmo tempo; devolve resultados e exceções."""
    barreira = threading.Barrier(len(tarefas))
    resultados, erros = [], []
    trava = threading.Lock()

    def rodar(tarefa):
        barreira.wait(timeout=30)
        try:
            valor = tarefa()
        except BaseException as erro:
            with trava:
                erros.append(erro)
            return
        with trava:
            resultados.append(valor)

    fios = [threading.Thread(target=rodar, args=(t,), daemon=True) for t in tarefas]
    for fio in fios:
        fio.start()
    for fio in fios:
        fio.join(timeout=TIMEOUT_FIO_S)
    assert not any(fio.is_alive() for fio in fios), "thread presa"
    return resultados, erros


class TestRajada:
    @pytest.mark.parametrize("executor_compartilhado", [True, False])
    def test_oito_threads_executam_cada_passo_uma_vez(
        self, montar_cenario, construir_executor, executor_compartilhado
    ):
        cenario = montar_cenario(atraso_s=0.3)
        if executor_compartilhado:
            tarefas = [cenario.executar] * 8
        else:
            registro = montar_registro(cenario.etapa)
            executores = [construir_executor(registro) for _ in range(8)]
            tarefas = [
                lambda e=e: e.executar(cenario.analise_id, cenario.user_id, "alfa")
                for e in executores
            ]

        resultados, erros = _disparar(tarefas)

        assert erros == []
        status = sorted(r.status for r in resultados)
        assert len(status) == 8
        assert status.count("concluida") == 1
        assert set(status) <= {"concluida", "em_execucao", "pulada"}
        assert cenario.etapa.contagens() == {"p1": 1, "p2": 1, "p3": 1}
        assert len({r.hash_entrada for r in resultados}) == 1
        (linha,) = cenario.linhas()
        assert linha["status"] == "concluida"
        assert cenario.executar().status == "pulada"

    def test_rajada_sobre_linha_falhada_refaz_apenas_uma_vez(self, montar_cenario):
        cenario = montar_cenario(atraso_s=0.3)
        cenario.etapa.falhas["p2"] = RuntimeError("quebrou")
        with pytest.raises(ErroPipeline):
            cenario.executar()
        cenario.etapa.falhas.clear()
        assert cenario.etapa.contagens() == {"p1": 1, "p2": 1, "p3": 0}

        resultados, erros = _disparar([cenario.executar] * 8)

        assert erros == []
        assert sum(r.status == "concluida" for r in resultados) == 1
        assert cenario.etapa.contagens() == {"p1": 1, "p2": 2, "p3": 1}
        (linha,) = cenario.linhas()
        assert linha["status"] == "concluida"

    def test_rajada_com_lease_vencido_retoma_uma_vez(self, montar_cenario):
        cenario = montar_cenario(atraso_s=0.3, limite_s=10, opcoes_executor={"lease_extra_s": 5})
        cenario.banco.inserir_execucao(
            cenario.analise_id,
            cenario.user_id,
            "alfa",
            "executando",
            hash_entrada=calcular_hash_entrada("alfa", 1, {}, {"semente": 1}),
            iniciado_ha_s=120,
        )

        resultados, erros = _disparar([cenario.executar] * 8)

        assert erros == []
        assert sum(r.status == "concluida" for r in resultados) == 1
        assert cenario.etapa.contagens() == {"p1": 1, "p2": 1, "p3": 1}
        assert len(cenario.linhas()) == 1


class TestHashesSimultaneos:
    def test_etapas_distintas_na_mesma_analise_nao_se_corrompem(
        self, dono, registrar_analise, etapa_de_teste, construir_executor, banco_pipeline
    ):
        alfa = etapa_de_teste("alfa", atraso_s=0.2, parametros=("semente",))
        beta = etapa_de_teste("beta", atraso_s=0.2, parametros=("semente",))
        analise_id, _ = registrar_analise(dono, {"semente": 3})
        executor = construir_executor(montar_registro(alfa, beta))

        resultados, erros = _disparar(
            [
                lambda: executor.executar(analise_id, dono, "alfa"),
                lambda: executor.executar(analise_id, dono, "beta"),
            ]
        )

        assert erros == []
        assert {r.status for r in resultados} == {"concluida"}
        assert len({r.hash_entrada for r in resultados}) == 2
        for nome, etapa in (("alfa", alfa), ("beta", beta)):
            assert etapa.contagens() == {"p1": 1, "p2": 1, "p3": 1}
            (linha,) = banco_pipeline.execucoes(analise_id, nome)
            assert linha["status"] == "concluida"

    def test_mesma_etapa_com_dois_hashes_termina_coerente(self, montar_cenario):
        cenario = montar_cenario()
        iniciou = threading.Event()

        def gancho(ctx, passo):
            iniciou.set()
            time.sleep(0.4)

        cenario.etapa.gancho = gancho
        desfecho_primeiro = []

        def primeiro():
            try:
                desfecho_primeiro.append(cenario.executar())
            except ErroPipeline as erro:
                desfecho_primeiro.append(erro)

        fio = threading.Thread(target=primeiro, daemon=True)
        fio.start()
        assert iniciou.wait(timeout=10)
        cenario.banco.definir_parametros(cenario.analise_id, {"semente": 2})
        resultados, erros = _disparar([cenario.executar])
        fio.join(timeout=TIMEOUT_FIO_S)

        assert not fio.is_alive()
        assert erros == []
        assert resultados[0].status == "concluida"
        assert len(desfecho_primeiro) == 1
        cenario.etapa.gancho = None
        final = cenario.executar()
        assert final.status in {"pulada", "concluida"}
        assert final.hash_entrada == resultados[0].hash_entrada
        linhas = {linha["hash_entrada"]: linha for linha in cenario.linhas()}
        assert len(linhas) == 2
        assert resultados[0].hash_entrada in linhas
        linha = linhas[final.hash_entrada]
        assert linha["status"] == "concluida"
        for i, passo in enumerate(PASSOS, start=1):
            (arquivo,) = linha["artefatos"][passo]["arquivos"]
            assert arquivo["sha256"] == sha256_de(cenario.caminho(f"alfa_p{i}.json").read_bytes())
