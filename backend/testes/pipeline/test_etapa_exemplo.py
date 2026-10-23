import json

import pytest

from app.pipeline.registro import registro_padrao
from app.pipeline.trava_gpu import CHAVE_GPU
from testes.pipeline.auxiliares import sha256_de
from testes.pipeline.conftest import Cenario

ETAPAS = ["exemplo", "exemplo_gpu"]


def _saidas(etapa: str) -> tuple[str, ...]:
    return tuple(f"{etapa}_p{n}.json" for n in (1, 2, 3))


@pytest.fixture
def montar(dono, registrar_analise, construir_executor, banco_pipeline, raiz_dados):
    executor = construir_executor(registro_padrao)

    def _montar(parametros=None):
        analise_id, video_id = registrar_analise(dono, parametros)
        return Cenario(dono, analise_id, video_id, None, executor, banco_pipeline, raiz_dados)

    return _montar


def _ler_saidas(cenario: Cenario, etapa: str = "exemplo") -> list[bytes]:
    return [cenario.caminho(nome).read_bytes() for nome in _saidas(etapa)]


class TestRegistroPadrao:
    @pytest.mark.parametrize(
        ("nome", "fila", "gpu"), [("exemplo", "cpu", False), ("exemplo_gpu", "gpu", True)]
    )
    def test_etapas_de_exemplo_declaradas(self, nome, fila, gpu):
        assert nome in registro_padrao
        etapa = registro_padrao.obter(nome)

        assert etapa.nome == nome
        assert etapa.versao == 1
        assert etapa.fila == fila
        assert etapa.usa_gpu is gpu
        assert etapa.parametros == ("semente",)
        assert etapa.entradas == ()
        assert [p.nome for p in etapa.passos] == ["p1", "p2", "p3"]
        assert [p.saidas for p in etapa.passos] == [(s,) for s in _saidas(nome)]


class TestExecucao:
    @pytest.mark.parametrize("etapa", ETAPAS)
    def test_ponta_a_ponta_gera_os_tres_json_do_contrato(self, montar, etapa):
        cenario = montar({"semente": 42})

        resultado = cenario.executar(etapa)

        assert resultado.status == "concluida"
        assert resultado.passos_executados == ("p1", "p2", "p3")
        brutos = _ler_saidas(cenario, etapa)
        p1, p2, p3 = (json.loads(b) for b in brutos)
        assert p1 == {"passo": 1, "semente": 42, "anterior": None}
        assert p2 == {"passo": 2, "semente": 42, "anterior": sha256_de(brutos[0])}
        assert p3 == {"passo": 3, "semente": 42, "anterior": sha256_de(brutos[1])}
        (linha,) = cenario.linhas(etapa)
        assert linha["status"] == "concluida"
        assert set(linha["artefatos"]) == {"p1", "p2", "p3"}

    @pytest.mark.parametrize("etapa", ETAPAS)
    def test_segunda_execucao_e_pulada(self, montar, etapa):
        cenario = montar({"semente": 5})
        cenario.executar(etapa)
        antes = _ler_saidas(cenario, etapa)

        resultado = cenario.executar(etapa)

        assert resultado.status == "pulada"
        assert _ler_saidas(cenario, etapa) == antes
        assert len(cenario.linhas(etapa)) == 1

    @pytest.mark.parametrize("etapa", ETAPAS)
    def test_semente_diferente_gera_artefatos_diferentes(self, montar, etapa):
        cenario = montar({"semente": 1})
        cenario.executar(etapa)
        antes = _ler_saidas(cenario, etapa)
        cenario.banco.definir_parametros(cenario.analise_id, {"semente": 2})

        resultado = cenario.executar(etapa)

        assert resultado.status == "concluida"
        depois = _ler_saidas(cenario, etapa)
        assert all(a != d for a, d in zip(antes, depois, strict=True))
        assert json.loads(depois[0])["semente"] == 2
        assert len(cenario.linhas(etapa)) == 2

    @pytest.mark.parametrize("etapa", ETAPAS)
    def test_mesma_semente_em_analises_distintas_gera_bytes_identicos(self, montar, etapa):
        primeira, segunda = montar({"semente": 11}), montar({"semente": 11})

        primeira.executar(etapa)
        segunda.executar(etapa)

        assert _ler_saidas(primeira, etapa) == _ler_saidas(segunda, etapa)

    @pytest.mark.parametrize(
        ("parametros", "esperado"),
        [
            ({}, None),
            ({"semente": None}, None),
            ({"semente": "ação 日本 ✓"}, "ação 日本 ✓"),
            ({"semente": 0}, 0),
        ],
    )
    def test_valores_de_borda_da_semente(self, montar, parametros, esperado):
        cenario = montar(parametros)

        cenario.executar("exemplo")

        p1, p2, p3 = (json.loads(b) for b in _ler_saidas(cenario))
        assert [p["semente"] for p in (p1, p2, p3)] == [esperado] * 3
        assert (p1["passo"], p2["passo"], p3["passo"]) == (1, 2, 3)

    def test_parametro_alheio_a_etapa_nao_reexecuta(self, montar):
        cenario = montar({"semente": 3, "outro": "a"})
        cenario.executar("exemplo")
        cenario.banco.definir_parametros(cenario.analise_id, {"semente": 3, "outro": "b"})

        assert cenario.executar("exemplo").status == "pulada"

    def test_etapa_gpu_libera_a_trava_ao_terminar(self, montar, redis_teste):
        cenario = montar({"semente": 1})

        cenario.executar("exemplo_gpu")

        assert not redis_teste.exists(CHAVE_GPU)

    def test_etapas_de_exemplo_sao_independentes_na_mesma_analise(self, montar):
        cenario = montar({"semente": 8})

        cpu = cenario.executar("exemplo")
        gpu = cenario.executar("exemplo_gpu")

        assert (cpu.status, gpu.status) == ("concluida", "concluida")
        assert cpu.hash_entrada != gpu.hash_entrada
        assert len(cenario.linhas("exemplo")) == len(cenario.linhas("exemplo_gpu")) == 1
