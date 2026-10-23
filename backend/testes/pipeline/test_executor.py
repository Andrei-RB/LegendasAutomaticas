import errno
import hashlib
import os
import threading
import time
import uuid
from collections.abc import Mapping

import pytest

from app.pipeline.erros import MENSAGENS, ErroPipeline
from app.pipeline.eventos import canal
from app.pipeline.executor import Etapa, Passo, RegistroEtapas
from app.pipeline.hashing import calcular_hash_entrada, canonizar
from app.pipeline.trava_gpu import CHAVE_GPU
from testes.pipeline.auxiliares import montar_registro, sha256_de
from testes.pipeline.conftest import Cenario

PASSOS = ("p1", "p2", "p3")


def _falha(cenario: Cenario, etapa: str | None = None) -> ErroPipeline:
    with pytest.raises(ErroPipeline) as capturado:
        cenario.executar(etapa)
    return capturado.value


def _arquivos(cenario: Cenario) -> list:
    pasta = cenario.diretorio()
    return [p for p in pasta.rglob("*") if p.is_file()] if pasta.exists() else []


class TestReexecucao:
    def test_primeira_execucao_conclui_e_registra_artefatos(self, cenario, armazenamento):
        resultado = cenario.executar()

        assert resultado.status == "concluida"
        assert resultado.passos_executados == PASSOS
        assert resultado.passos_reaproveitados == ()
        esperado = calcular_hash_entrada("alfa", 1, {}, {"semente": 1})
        assert resultado.hash_entrada == esperado
        (linha,) = cenario.linhas()
        assert linha["status"] == "concluida"
        assert linha["hash_entrada"] == esperado
        assert linha["user_id"] == cenario.user_id
        assert linha["iniciado_em"] is not None
        assert linha["concluido_em"] is not None
        for indice, passo in enumerate(PASSOS, start=1):
            nome = f"alfa_p{indice}.json"
            (arquivo,) = linha["artefatos"][passo]["arquivos"]
            dados = cenario.caminho(nome).read_bytes()
            assert arquivo == {"nome": nome, "sha256": sha256_de(dados), "bytes": len(dados)}
            assert armazenamento.verificar(
                cenario.user_id, cenario.video_id, f"{cenario.analise_id}/{nome}", sha256_de(dados)
            )
            metrica = linha["metricas"]["passos"][passo]
            assert metrica["execucoes"] == 1
            assert isinstance(metrica["duracao_s"], float)
            assert metrica["duracao_s"] >= 0

    def test_mesma_entrada_nao_reexecuta(self, cenario):
        primeiro = cenario.executar()
        antes = cenario.etapa.contagens()

        segundo = cenario.executar()

        assert antes == {"p1": 1, "p2": 1, "p3": 1}
        assert segundo.status == "pulada"
        assert segundo.hash_entrada == primeiro.hash_entrada
        assert segundo.passos_executados == ()
        assert cenario.etapa.contagens() == antes
        assert len(cenario.linhas()) == 1

    def test_parametro_declarado_alterado_reexecuta(self, cenario):
        primeiro = cenario.executar()
        cenario.banco.definir_parametros(cenario.analise_id, {"semente": 2})

        segundo = cenario.executar()

        assert segundo.status == "concluida"
        assert segundo.hash_entrada != primeiro.hash_entrada
        assert segundo.passos_executados == PASSOS
        assert cenario.etapa.contagens() == {"p1": 2, "p2": 2, "p3": 2}
        linhas = cenario.linhas()
        assert len(linhas) == 2
        assert {linha["status"] for linha in linhas} == {"concluida"}
        assert {linha["hash_entrada"] for linha in linhas} == {
            primeiro.hash_entrada,
            segundo.hash_entrada,
        }

    def test_parametro_nao_declarado_alterado_nao_reexecuta(self, montar_cenario):
        cenario = montar_cenario(parametros={"semente": 1, "rotulo": "a"})
        cenario.executar()
        cenario.banco.definir_parametros(cenario.analise_id, {"semente": 1, "rotulo": "b"})

        resultado = cenario.executar()

        assert resultado.status == "pulada"
        assert cenario.etapa.contagens() == {"p1": 1, "p2": 1, "p3": 1}
        assert len(cenario.linhas()) == 1

    def test_parametro_declarado_ausente_vale_none(self, montar_cenario):
        cenario = montar_cenario(parametros={"outro": 3})

        resultado = cenario.executar()

        assert resultado.hash_entrada == calcular_hash_entrada("alfa", 1, {}, {"semente": None})

    @pytest.mark.parametrize(("antes", "depois"), [(1, "1"), (True, 1), (None, 0), ("a", "A")])
    def test_tipo_do_parametro_faz_parte_do_hash(self, montar_cenario, antes, depois):
        cenario = montar_cenario(parametros={"semente": antes})
        primeiro = cenario.executar()
        cenario.banco.definir_parametros(cenario.analise_id, {"semente": depois})

        segundo = cenario.executar()

        assert segundo.status == "concluida"
        assert segundo.hash_entrada != primeiro.hash_entrada
        assert len(cenario.linhas()) == 2

    def test_versao_nova_da_etapa_reexecuta(self, cenario, etapa_de_teste, construir_executor):
        primeiro = cenario.executar()
        nova = etapa_de_teste("alfa", versao=2, parametros=("semente",))
        executor_novo = construir_executor(montar_registro(nova))

        segundo = executor_novo.executar(cenario.analise_id, cenario.user_id, "alfa")

        assert segundo.status == "concluida"
        assert segundo.hash_entrada != primeiro.hash_entrada
        assert nova.contagens() == {"p1": 1, "p2": 1, "p3": 1}
        assert len(cenario.linhas()) == 2


class TestFalhaERetomada:
    def test_falha_no_passo_2_retoma_do_passo_2(self, cenario):
        cenario.etapa.falhas["p2"] = RuntimeError("quebrou")
        erro = _falha(cenario)

        assert erro.codigo == "INTERNO"
        assert cenario.etapa.contagens() == {"p1": 1, "p2": 1, "p3": 0}
        (linha,) = cenario.linhas()
        assert linha["status"] == "falhou"
        assert set(linha["artefatos"]) == {"p1"}
        assert linha["metricas"]["erro_codigo"] == "INTERNO"
        assert cenario.caminho("alfa_p1.json").exists()
        assert not cenario.caminho("alfa_p2.json").exists()

        cenario.etapa.falhas.clear()
        resultado = cenario.executar()

        assert resultado.status == "concluida"
        assert resultado.passos_executados == ("p2", "p3")
        assert resultado.passos_reaproveitados == ("p1",)
        assert cenario.etapa.contagens() == {"p1": 1, "p2": 2, "p3": 1}
        (linha,) = cenario.linhas()
        assert linha["status"] == "concluida"
        assert set(linha["artefatos"]) == set(PASSOS)
        passos = linha["metricas"]["passos"]
        assert passos["p1"]["execucoes"] == 1
        assert passos["p3"]["execucoes"] == 1
        assert passos["p2"]["execucoes"] in (1, 2)

    def test_registros_dos_passos_seguintes_a_um_invalido_sao_descartados(self, cenario):
        cenario.executar()
        cenario.caminho("alfa_p1.json").write_bytes(b'{"adulterado": true}')
        cenario.etapa.falhas["p2"] = RuntimeError("quebrou")

        _falha(cenario)

        (linha,) = cenario.linhas()
        assert linha["status"] == "falhou"
        assert set(linha["artefatos"]) == {"p1"}

    def test_registro_sem_as_saidas_declaradas_refaz_o_passo(self, cenario):
        from sqlalchemy import text

        cenario.executar()
        with cenario.banco.motor.begin() as con:
            con.execute(
                text(
                    "UPDATE execucoes_etapa SET artefatos = "
                    "jsonb_set(artefatos, '{p2,arquivos}', '[]') WHERE analise_id = :a"
                ),
                {"a": cenario.analise_id},
            )

        resultado = cenario.executar()

        assert resultado.status == "concluida"
        assert resultado.passos_executados == ("p2", "p3")
        assert resultado.passos_reaproveitados == ("p1",)

    def test_falha_antiga_nao_impede_novo_hash(self, cenario):
        cenario.etapa.falhas["p1"] = RuntimeError("quebrou")
        _falha(cenario)
        cenario.etapa.falhas.clear()
        cenario.banco.definir_parametros(cenario.analise_id, {"semente": 9})

        resultado = cenario.executar()

        assert resultado.status == "concluida"
        assert sorted(linha["status"] for linha in cenario.linhas()) == ["concluida", "falhou"]

    @pytest.mark.parametrize("modo", ["alterar", "apagar"])
    @pytest.mark.parametrize("adulterado", PASSOS)
    def test_artefato_adulterado_refaz_o_passo_e_os_seguintes(self, cenario, adulterado, modo):
        cenario.executar()
        indice = PASSOS.index(adulterado) + 1
        alvo = cenario.caminho(f"alfa_p{indice}.json")
        if modo == "alterar":
            alvo.write_bytes(b'{"adulterado": true}')
        else:
            alvo.unlink()

        resultado = cenario.executar()

        assert resultado.status == "concluida"
        assert resultado.passos_executados == PASSOS[indice - 1 :]
        assert resultado.passos_reaproveitados == PASSOS[: indice - 1]
        esperado = {passo: 1 if i < indice else 2 for i, passo in enumerate(PASSOS, start=1)}
        assert cenario.etapa.contagens() == esperado
        (linha,) = cenario.linhas()
        assert linha["status"] == "concluida"
        for i, passo in enumerate(PASSOS, start=1):
            (arquivo,) = linha["artefatos"][passo]["arquivos"]
            assert arquivo["sha256"] == sha256_de(cenario.caminho(f"alfa_p{i}.json").read_bytes())


@pytest.fixture
def par(dono, registrar_analise, etapa_de_teste, construir_executor, banco_pipeline, raiz_dados):
    base = etapa_de_teste("base", parametros=("semente",))
    derivada = etapa_de_teste("derivada", entradas=("base",), leituras_montante=("base_p3.json",))
    analise_id, video_id = registrar_analise(dono, {"semente": 1})
    executor = construir_executor(montar_registro(base, derivada))

    def _cenario(etapa):
        return Cenario(dono, analise_id, video_id, etapa, executor, banco_pipeline, raiz_dados)

    return _cenario(base), _cenario(derivada)


def _hash_da_montante(linha: dict) -> str:
    arquivos = {
        a["nome"]: a["sha256"] for passo in linha["artefatos"].values() for a in passo["arquivos"]
    }
    return hashlib.sha256(canonizar(arquivos)).hexdigest()


class TestDependenciaEntreEtapas:
    def test_hash_da_jusante_usa_os_artefatos_da_montante(self, par):
        base, derivada = par
        base.executar()
        (linha_base,) = base.linhas()

        resultado = derivada.executar()

        esperado = calcular_hash_entrada("derivada", 1, {"base": _hash_da_montante(linha_base)}, {})
        assert resultado.status == "concluida"
        assert resultado.hash_entrada == esperado

    def test_mudanca_a_montante_reexecuta_a_jusante(self, par):
        base, derivada = par
        base.executar()
        primeiro = derivada.executar()
        base.banco.definir_parametros(base.analise_id, {"semente": 2})
        assert base.executar().status == "concluida"

        segundo = derivada.executar()

        assert segundo.status == "concluida"
        assert segundo.hash_entrada != primeiro.hash_entrada
        assert derivada.etapa.contagens() == {"p1": 2, "p2": 2, "p3": 2}
        assert len(derivada.linhas()) == 2

    def test_montante_inalterada_mantem_a_jusante_pulada(self, par):
        base, derivada = par
        base.executar()
        derivada.executar()
        assert base.executar().status == "pulada"

        resultado = derivada.executar()

        assert resultado.status == "pulada"
        assert derivada.etapa.contagens() == {"p1": 1, "p2": 1, "p3": 1}

    def test_sem_a_montante_a_entrada_esta_ausente(self, par):
        _, derivada = par

        erro = _falha(derivada)

        assert erro.codigo == "ENTRADA_AUSENTE"
        assert derivada.linhas() == []
        assert derivada.etapa.contagens() == {"p1": 0, "p2": 0, "p3": 0}

    @pytest.mark.parametrize("modo", ["alterar", "apagar"])
    def test_artefato_da_montante_adulterado_conta_como_ausente(self, par, modo):
        base, derivada = par
        base.executar()
        alvo = base.caminho("base_p2.json")
        if modo == "alterar":
            alvo.write_bytes(b"{}")
        else:
            alvo.unlink()

        erro = _falha(derivada)

        assert erro.codigo == "ENTRADA_AUSENTE"
        assert derivada.linhas() == []
        assert derivada.etapa.contagens() == {"p1": 0, "p2": 0, "p3": 0}

    def test_montante_que_so_falhou_conta_como_ausente(self, par):
        base, derivada = par
        base.etapa.falhas["p2"] = RuntimeError("quebrou")
        _falha(base)

        erro = _falha(derivada)

        assert erro.codigo == "ENTRADA_AUSENTE"
        assert derivada.etapa.contagens() == {"p1": 0, "p2": 0, "p3": 0}


class TestGravacaoEPassosInvalidos:
    def test_falha_na_gravacao_atomica_nao_deixa_arquivo_parcial(self, cenario):
        def parcial(ctx):
            with ctx.gravacao_atomica("alfa_p1.json") as gravacao:
                gravacao.caminho.write_bytes(b'{"parcial"')
                raise OSError(errno.ENOSPC, "sem espaço")

        cenario.etapa.comportamentos["p1"] = parcial

        erro = _falha(cenario)

        assert erro.codigo == "ARMAZENAMENTO"
        assert _arquivos(cenario) == []
        (linha,) = cenario.linhas()
        assert linha["status"] == "falhou"

    def test_falha_no_replace_nao_deixa_arquivo_parcial(self, cenario, monkeypatch):
        original = os.replace

        def replace_com_falha(origem, destino, *args, **kwargs):
            if str(cenario.raiz) in str(destino):
                raise OSError(errno.EIO, "falha de disco")
            return original(origem, destino, *args, **kwargs)

        monkeypatch.setattr(os, "replace", replace_com_falha)

        erro = _falha(cenario)

        assert erro.codigo == "ARMAZENAMENTO"
        assert _arquivos(cenario) == []
        assert cenario.etapa.contar("p2") == 0

    @pytest.mark.parametrize("via", ["gravar", "gravacao_atomica"])
    def test_passo_que_grava_nome_nao_declarado_falha_interno(self, cenario, via):
        def indevido(ctx):
            ctx.gravar("alfa_p1.json", b"{}")
            if via == "gravar":
                ctx.gravar("estranho.json", b"{}")
            else:
                with ctx.gravacao_atomica("estranho.json") as gravacao:
                    gravacao.caminho.write_bytes(b"{}")

        cenario.etapa.comportamentos["p1"] = indevido

        erro = _falha(cenario)

        assert erro.codigo == "INTERNO"
        assert not cenario.caminho("estranho.json").exists()
        assert cenario.etapa.contar("p2") == 0
        (linha,) = cenario.linhas()
        assert linha["status"] == "falhou"
        assert "p1" not in linha["artefatos"]

    def test_passo_que_nao_gera_a_saida_declarada_falha_interno(self, cenario):
        cenario.etapa.comportamentos["p2"] = lambda ctx: None

        erro = _falha(cenario)

        assert erro.codigo == "INTERNO"
        assert cenario.etapa.contagens() == {"p1": 1, "p2": 1, "p3": 0}
        (linha,) = cenario.linhas()
        assert linha["status"] == "falhou"
        assert set(linha["artefatos"]) == {"p1"}

    def test_contexto_expoe_ids_e_so_os_parametros_declarados(self, montar_cenario):
        cenario = montar_cenario(parametros={"semente": 7, "segredo": "x"})
        vistos = {}

        def gancho(ctx, passo):
            vistos["ids"] = (ctx.user_id, ctx.video_id, ctx.analise_id)
            vistos["parametros"] = ctx.parametros
            if passo == "p2":
                vistos["caminho"] = ctx.caminho("alfa_p1.json").read_bytes() == ctx.ler(
                    "alfa_p1.json"
                )

        cenario.etapa.gancho = gancho
        cenario.executar()

        assert vistos["ids"] == (cenario.user_id, cenario.video_id, cenario.analise_id)
        assert isinstance(vistos["parametros"], Mapping)
        assert dict(vistos["parametros"]) == {"semente": 7}
        assert vistos["caminho"] is True

    def test_nenhuma_transacao_fica_aberta_durante_o_passo(self, cenario):
        abertas = []
        cenario.etapa.gancho = lambda ctx, passo: abertas.append(cenario.banco.transacoes_abertas())

        cenario.executar()

        assert abertas == [0, 0, 0]


class TestDesconhecidos:
    def test_outro_usuario_nao_executa_analise_alheia(
        self, cenario, outro_dono, capturar_eventos, raiz_dados
    ):
        captura = capturar_eventos()

        with pytest.raises(ErroPipeline) as capturado:
            cenario.executor.executar(cenario.analise_id, outro_dono, "alfa")

        assert capturado.value.codigo == "ANALISE_INEXISTENTE"
        assert cenario.banco.execucoes(cenario.analise_id) == []
        assert not raiz_dados.exists() or not list(raiz_dados.rglob("*"))
        assert captura.aguardar(1, timeout=0.5) == []
        assert cenario.etapa.contagens() == {"p1": 0, "p2": 0, "p3": 0}
        analise = cenario.banco.analise(cenario.analise_id)
        assert (analise["status"], analise["etapa_atual"]) == ("pendente", None)

    def test_analise_inexistente(self, cenario, dono, raiz_dados):
        with pytest.raises(ErroPipeline) as capturado:
            cenario.executor.executar(uuid.uuid4(), dono, "alfa")

        assert capturado.value.codigo == "ANALISE_INEXISTENTE"
        assert not raiz_dados.exists() or not list(raiz_dados.rglob("*"))

    @pytest.mark.parametrize("nome", ["inexistente", "../../etc/passwd", "ALFA", ""])
    def test_etapa_desconhecida(self, cenario, nome):
        erro = _falha(cenario, nome)

        assert erro.codigo == "ETAPA_DESCONHECIDA"
        assert cenario.banco.execucoes(cenario.analise_id) == []
        assert cenario.etapa.contagens() == {"p1": 0, "p2": 0, "p3": 0}


class TestEventos:
    def test_execucao_completa_publica_a_sequencia_esperada(self, cenario, capturar_eventos):
        captura = capturar_eventos()

        cenario.executar()

        eventos = captura.aguardar(5)
        assert [e["tipo"] for e in eventos] == [
            "etapa_iniciada",
            "passo_concluido",
            "passo_concluido",
            "passo_concluido",
            "etapa_concluida",
        ]
        assert [e["passo"] for e in eventos[1:4]] == list(PASSOS)
        assert [e["progresso_etapa"] for e in eventos[1:4]] == [33.3, 66.7, 100.0]
        assert eventos[0]["progresso_etapa"] == 0
        assert eventos[4]["progresso_etapa"] == 100.0
        assert {e["analise_id"] for e in eventos} == {str(cenario.analise_id)}
        assert {e["etapa"] for e in eventos} == {"alfa"}
        esperado = canal(cenario.user_id, cenario.analise_id)
        assert {c for c, _ in captura.itens} == {esperado}

    def test_etapa_pulada_publica_apenas_etapa_pulada(self, cenario, capturar_eventos):
        cenario.executar()
        captura = capturar_eventos()

        cenario.executar()

        eventos = captura.aguardar(1)
        assert [e["tipo"] for e in eventos] == ["etapa_pulada"]
        assert eventos[0]["etapa"] == "alfa"

    def test_falha_publica_evento_de_erro_com_codigo_e_mensagem(self, cenario, capturar_eventos):
        captura = capturar_eventos()
        cenario.etapa.falhas["p2"] = RuntimeError("quebrou")

        _falha(cenario)

        eventos = captura.aguardar(3)
        assert [e["tipo"] for e in eventos] == ["etapa_iniciada", "passo_concluido", "erro"]
        assert eventos[1]["passo"] == "p1"
        assert eventos[2]["codigo"] == "INTERNO"
        assert eventos[2]["mensagem"] == MENSAGENS["INTERNO"]
        assert eventos[2]["etapa"] == "alfa"

    def test_estado_da_analise_acompanha_a_execucao(self, cenario):
        observado = []

        def gancho(ctx, passo):
            analise = cenario.banco.analise(cenario.analise_id)
            observado.append(
                (passo, analise["status"], analise["etapa_atual"], analise["erro_amigavel"])
            )

        cenario.etapa.gancho = gancho
        cenario.etapa.falhas["p2"] = RuntimeError("quebrou")
        _falha(cenario)

        analise = cenario.banco.analise(cenario.analise_id)
        assert analise["status"] == "falhou"
        assert analise["etapa_atual"] == "alfa"
        assert analise["erro_amigavel"] == MENSAGENS["INTERNO"]
        assert observado == [
            ("p1", "processando", "alfa", None),
            ("p2", "processando", "alfa", None),
        ]

        observado.clear()
        cenario.etapa.falhas.clear()
        cenario.executar()

        assert observado == [
            ("p2", "processando", "alfa", None),
            ("p3", "processando", "alfa", None),
        ]
        assert cenario.banco.analise(cenario.analise_id)["erro_amigavel"] is None


class TestLease:
    def test_lease_vencido_e_retomado(self, montar_cenario):
        cenario = montar_cenario(limite_s=10, opcoes_executor={"lease_extra_s": 5})
        hash_entrada = calcular_hash_entrada("alfa", 1, {}, {"semente": 1})
        cenario.banco.inserir_execucao(
            cenario.analise_id,
            cenario.user_id,
            "alfa",
            "executando",
            hash_entrada=hash_entrada,
            iniciado_ha_s=60,
        )

        resultado = cenario.executar()

        assert resultado.status == "concluida"
        assert cenario.etapa.contagens() == {"p1": 1, "p2": 1, "p3": 1}
        (linha,) = cenario.linhas()
        assert linha["status"] == "concluida"

    @pytest.mark.parametrize(("iniciado_ha_s", "limite_s", "extra"), [(1, 10, 5), (100, 10, 300)])
    def test_lease_vigente_devolve_em_execucao_sem_alterar_o_banco(
        self, montar_cenario, capturar_eventos, iniciado_ha_s, limite_s, extra
    ):
        cenario = montar_cenario(limite_s=limite_s, opcoes_executor={"lease_extra_s": extra})
        hash_entrada = calcular_hash_entrada("alfa", 1, {}, {"semente": 1})
        cenario.banco.inserir_execucao(
            cenario.analise_id,
            cenario.user_id,
            "alfa",
            "executando",
            hash_entrada=hash_entrada,
            iniciado_ha_s=iniciado_ha_s,
            metricas={"marca": "original"},
        )
        antes = cenario.linhas()
        analise_antes = cenario.banco.analise(cenario.analise_id)
        captura = capturar_eventos()

        resultado = cenario.executar()

        assert resultado.status == "em_execucao"
        assert resultado.hash_entrada == hash_entrada
        assert cenario.etapa.contagens() == {"p1": 0, "p2": 0, "p3": 0}
        assert cenario.linhas() == antes
        assert cenario.banco.analise(cenario.analise_id) == analise_antes
        assert captura.aguardar(1, timeout=0.5) == []


class TestGpu:
    def test_trava_existe_durante_os_passos_e_some_depois(self, montar_cenario, redis_teste):
        cenario = montar_cenario(usa_gpu=True, fila="gpu")
        vistas = []
        cenario.etapa.gancho = lambda ctx, passo: vistas.append(redis_teste.exists(CHAVE_GPU))
        assert not redis_teste.exists(CHAVE_GPU)

        cenario.executar()

        assert vistas == [1, 1, 1]
        assert not redis_teste.exists(CHAVE_GPU)

    def test_etapa_sem_gpu_nao_toma_a_trava(self, cenario, redis_teste):
        vistas = []
        cenario.etapa.gancho = lambda ctx, passo: vistas.append(redis_teste.exists(CHAVE_GPU))

        cenario.executar()

        assert vistas == [0, 0, 0]

    def test_trava_liberada_apos_falha(self, montar_cenario, redis_teste):
        cenario = montar_cenario(usa_gpu=True, fila="gpu")
        cenario.etapa.falhas["p2"] = RuntimeError("quebrou")

        _falha(cenario)

        assert not redis_teste.exists(CHAVE_GPU)

    def test_duas_analises_gpu_nunca_sobrepoem_passos(
        self,
        dono,
        registrar_analise,
        etapa_de_teste,
        construir_executor,
        novas_chamadas,
    ):
        chamadas = novas_chamadas()
        etapa = etapa_de_teste("gpuum", usa_gpu=True, fila="gpu", atraso_s=0.3, chamadas=chamadas)
        executor = construir_executor(montar_registro(etapa))
        analises = [registrar_analise(dono)[0] for _ in range(2)]
        resultados = {}
        erros = []

        def rodar(analise_id):
            try:
                resultados[analise_id] = executor.executar(analise_id, dono, "gpuum")
            except Exception as erro:
                erros.append(erro)

        fios = [threading.Thread(target=rodar, args=(a,)) for a in analises]
        for fio in fios:
            fio.start()
        for fio in fios:
            fio.join(timeout=60)

        assert not any(fio.is_alive() for fio in fios)
        assert erros == []
        assert {r.status for r in resultados.values()} == {"concluida"}
        assert etapa.contagens() == {"p1": 2, "p2": 2, "p3": 2}
        assert chamadas.max_ativos == 1

    def test_trava_ocupada_por_outro_dono_indisponibiliza_a_gpu(self, montar_cenario, redis_teste):
        cenario = montar_cenario(usa_gpu=True, fila="gpu", opcoes_executor={"trava_espera_s": 0.6})
        redis_teste.set(CHAVE_GPU, "outro-dono", px=60_000)
        inicio = time.monotonic()

        erro = _falha(cenario)

        assert erro.codigo == "GPU_INDISPONIVEL"
        assert 0.5 <= time.monotonic() - inicio < 15
        (linha,) = cenario.linhas()
        assert linha["status"] == "falhou"
        assert cenario.etapa.contagens() == {"p1": 0, "p2": 0, "p3": 0}
        assert redis_teste.get(CHAVE_GPU) == b"outro-dono"
        analise = cenario.banco.analise(cenario.analise_id)
        assert analise["status"] == "falhou"
        assert analise["erro_amigavel"] == MENSAGENS["GPU_INDISPONIVEL"]

    def test_trava_perdida_antes_de_gravar_o_passo_falha(self, montar_cenario, redis_teste):
        cenario = montar_cenario(usa_gpu=True, fila="gpu", opcoes_executor={"trava_ttl_ms": 600})

        def gancho(ctx, passo):
            if passo == "p1":
                redis_teste.delete(CHAVE_GPU)
                time.sleep(1.2)

        cenario.etapa.gancho = gancho

        erro = _falha(cenario)

        assert erro.codigo == "GPU_INDISPONIVEL"
        assert cenario.etapa.contar("p2") == 0
        (linha,) = cenario.linhas()
        assert linha["status"] == "falhou"
        assert not redis_teste.exists(CHAVE_GPU)

    def test_verificar_trava_no_passo_detecta_a_perda(self, montar_cenario, redis_teste):
        cenario = montar_cenario(usa_gpu=True, fila="gpu", opcoes_executor={"trava_ttl_ms": 600})
        ok_antes = []

        def gancho(ctx, passo):
            ctx.verificar_trava()
            ok_antes.append(True)
            redis_teste.delete(CHAVE_GPU)
            time.sleep(1.2)
            ctx.verificar_trava()

        cenario.etapa.gancho = gancho

        erro = _falha(cenario)

        assert ok_antes == [True]
        assert erro.codigo == "GPU_INDISPONIVEL"


class TestEtapaEhRegistro:
    BASE = {
        "nome": "alfa",
        "versao": 1,
        "fila": "cpu",
        "passos": (Passo("p1", ("a.json",), lambda ctx: None),),
    }

    @staticmethod
    def _passo(nome="p1", saidas=("a.json",)):
        return Passo(nome, saidas, lambda ctx: None)

    @pytest.mark.parametrize(
        "campos",
        [
            {"nome": "Alfa"},
            {"nome": "1alfa"},
            {"nome": ""},
            {"nome": "a" * 33},
            {"nome": "alfa-beta"},
            {"nome": "alfá"},
            {"fila": "outra"},
            {"fila": ""},
            {"passos": ()},
            {"passos": (_passo("p1"), _passo("p1", ("b.json",)))},
            {"passos": (_passo("P1"),)},
            {"passos": (_passo("p" * 33),)},
            {"passos": (_passo(saidas=("../fora.json",)),)},
            {"passos": (_passo(saidas=("/abs.json",)),)},
            {"passos": (_passo(saidas=("",)),)},
            {"passos": (_passo(saidas=("a\\b.json",)),)},
        ],
        ids=lambda c: "-".join(f"{k}={str(v)[:12]}" for k, v in c.items()),
    )
    def test_etapa_invalida_levanta_value_error(self, campos):
        with pytest.raises(ValueError):
            Etapa(**{**self.BASE, **campos})

    @pytest.mark.parametrize("fila", ["gpu", "cpu", "ai", "render"])
    def test_filas_validas(self, fila):
        etapa = Etapa(**{**self.BASE, "fila": fila, "nome": "a" * 32})

        assert etapa.fila == fila

    def test_registro_obtem_registrada_e_recusa_desconhecida(self):
        registro = RegistroEtapas()
        etapa = Etapa(**self.BASE)
        registro.registrar(etapa)

        assert "alfa" in registro
        assert "beta" not in registro
        assert registro.obter("alfa") is etapa
        with pytest.raises(ErroPipeline) as capturado:
            registro.obter("beta")
        assert capturado.value.codigo == "ETAPA_DESCONHECIDA"

    def test_registro_recusa_saida_repetida_entre_etapas(self):
        registro = RegistroEtapas()
        registro.registrar(Etapa(**self.BASE))
        outra = Etapa(**{**self.BASE, "nome": "beta"})

        with pytest.raises(ValueError):
            registro.registrar(outra)
        assert "beta" not in registro

    def test_registro_padrao_nao_repete_saidas_entre_etapas(self):
        from app.pipeline.registro import registro_padrao

        nomes = [s for e in registro_padrao._etapas.values() for p in e.passos for s in p.saidas]

        assert len(nomes) == len(set(nomes))
