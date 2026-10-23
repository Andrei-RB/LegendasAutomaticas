import json
import time
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from app.nucleo.config import settings
from app.pipeline.eventos import EventoAnalise, canal
from testes.auxiliares_auth import adulterar_carga, decodificar, montar_token, trocar_assinatura
from testes.pipeline.auxiliares import caminho_eventos, esperar_ate

CHAVES_ESTADO = {"analise_id", "status", "etapa_atual", "progresso", "erro", "etapas"}


def _evento(analise_id, tipo="passo_concluido", **campos) -> EventoAnalise:
    return EventoAnalise(tipo=tipo, analise_id=analise_id, **campos)


def _abrir(servidor, analise_id, token):
    leitor = servidor.abrir(analise_id, token)
    assert leitor.aguardar_resposta() == 200
    quadro = leitor.proximo()
    assert quadro.evento == "estado"
    return leitor, quadro


class TestAutenticacao:
    def test_sem_cookie_responde_401(self, servidor_http, analise_a):
        resposta = servidor_http.get(caminho_eventos(analise_a))

        assert resposta.status_code == 401
        assert str(analise_a) not in resposta.text

    @pytest.mark.parametrize(
        "forma",
        ["carga_adulterada", "assinatura_trocada", "expirado", "chave_errada", "sem_assinatura"],
    )
    def test_token_invalido_responde_401(self, servidor_http, usuario_a, analise_a, forma):
        valido = servidor_http.login(usuario_a)
        sub = usuario_a.id
        token = {
            "carga_adulterada": lambda: adulterar_carga(valido, sub=str(uuid.uuid4())),
            "assinatura_trocada": lambda: trocar_assinatura(valido),
            "expirado": lambda: montar_token(sub, expira_em=-30),
            "chave_errada": lambda: montar_token(sub, chave="x" * 64),
            "sem_assinatura": lambda: montar_token(sub, algoritmo="none"),
        }[forma]()

        resposta = servidor_http.get(caminho_eventos(analise_a), token)

        assert resposta.status_code == 401
        assert str(analise_a) not in resposta.text

    def test_token_revogado_pelo_logout_responde_401(self, servidor_http, token_a, analise_a):
        assert servidor_http.logout(token_a).status_code == 204

        resposta = servidor_http.get(caminho_eventos(analise_a), token_a)

        assert resposta.status_code == 401

    def test_analise_inexistente_e_de_outro_dono_dao_o_mesmo_404(
        self, servidor_http, token_a, token_b, analise_a, analise_b
    ):
        inexistente = uuid.uuid4()

        sem_registro = servidor_http.get(caminho_eventos(inexistente), token_a)
        alheia = servidor_http.get(caminho_eventos(analise_b), token_a)
        alheia_inversa = servidor_http.get(caminho_eventos(analise_a), token_b)

        assert sem_registro.status_code == alheia.status_code == alheia_inversa.status_code == 404
        assert sem_registro.content == alheia.content == alheia_inversa.content
        for resposta, ids in (
            (sem_registro, inexistente),
            (alheia, analise_b),
            (alheia_inversa, analise_a),
        ):
            assert str(ids) not in resposta.text

    @pytest.mark.parametrize(
        "valor", ["nao-e-uuid", "123", "zzzzzzzz-zzzz-zzzz-zzzz-zzzzzzzzzzzz", "%3Cscript%3E"]
    )
    def test_uuid_invalido_responde_422(self, servidor_http, token_a, valor):
        resposta = servidor_http.get(f"/api/v1/analises/{valor}/eventos", token_a)

        assert resposta.status_code == 422


class TestQuadros:
    def test_cabecalhos_da_resposta(self, servidor_http, token_a, analise_a):
        leitor, _ = _abrir(servidor_http, analise_a, token_a)

        cabecalhos = leitor.cabecalhos

        assert cabecalhos["content-type"] == "text/event-stream; charset=utf-8"
        assert cabecalhos["cache-control"] == "no-store"
        assert cabecalhos["x-accel-buffering"] == "no"
        assert cabecalhos["x-content-type-options"] == "nosniff"
        assert cabecalhos["x-frame-options"] == "DENY"
        assert cabecalhos["referrer-policy"] == "no-referrer"
        assert cabecalhos["content-security-policy"].startswith("default-src 'none'")

    def test_primeiro_quadro_traz_o_estado_inicial(self, servidor_http, token_a, analise_a):
        _, quadro = _abrir(servidor_http, analise_a, token_a)

        estado = quadro.json
        assert len(quadro.dados) == 1
        assert set(estado) == CHAVES_ESTADO
        assert estado == {
            "analise_id": str(analise_a),
            "status": "pendente",
            "etapa_atual": None,
            "progresso": 0,
            "erro": None,
            "etapas": [],
        }

    def test_estado_reflete_o_banco_e_a_ultima_linha_por_etapa(
        self, servidor_http, token_a, dono, analise_a, banco_pipeline, registrar_analise
    ):
        agora = datetime.now(UTC)
        banco_pipeline.definir_analise(
            analise_a,
            status="processando",
            etapa_atual="beta",
            progresso=40.5,
            erro_amigavel="Mensagem pública.",
        )
        banco_pipeline.inserir_execucao(
            analise_a,
            dono,
            "alfa",
            "falhou",
            criado_em=agora - timedelta(hours=2),
            iniciado_ha_s=7200,
        )
        banco_pipeline.inserir_execucao(
            analise_a,
            dono,
            "alfa",
            "concluida",
            criado_em=agora - timedelta(hours=1),
            iniciado_ha_s=3600,
        )
        banco_pipeline.inserir_execucao(analise_a, dono, "beta", "executando", iniciado_ha_s=10)
        outra, _ = registrar_analise(dono)
        banco_pipeline.inserir_execucao(outra, dono, "gama", "concluida")

        _, quadro = _abrir(servidor_http, analise_a, token_a)

        estado = quadro.json
        assert estado["status"] == "processando"
        assert estado["etapa_atual"] == "beta"
        assert estado["progresso"] == 40.5
        assert estado["erro"] == "Mensagem pública."
        assert sorted(estado["etapas"], key=lambda e: e["etapa"]) == [
            {"etapa": "alfa", "status": "concluida"},
            {"etapa": "beta", "status": "executando"},
        ]

    def test_eventos_do_dono_chegam_em_ordem(
        self, servidor_http, token_a, dono, analise_a, publicar
    ):
        leitor, _ = _abrir(servidor_http, analise_a, token_a)
        enviados = [
            _evento(analise_a, passo=f"p{i}", etapa="alfa", progresso_etapa=i * 5)
            for i in range(1, 21)
        ]

        for evento in enviados:
            publicar(dono, analise_a, evento)

        recebidos = [leitor.proximo(5) for _ in enviados]
        assert [q.evento for q in recebidos] == ["passo_concluido"] * 20
        assert [EventoAnalise.model_validate_json(q.dados[0]) for q in recebidos] == enviados

    @pytest.mark.parametrize(
        "tipo", ["etapa_iniciada", "passo_concluido", "etapa_concluida", "etapa_pulada", "erro"]
    )
    def test_nome_do_evento_vem_do_tipo(
        self, servidor_http, token_a, dono, analise_a, publicar, tipo
    ):
        leitor, _ = _abrir(servidor_http, analise_a, token_a)

        publicar(dono, analise_a, _evento(analise_a, tipo, etapa="alfa"))

        quadro = leitor.proximo(5)
        assert quadro.evento == tipo
        assert quadro.json["tipo"] == tipo

    def test_mensagem_com_quebras_de_linha_nao_quebra_o_enquadramento(
        self, servidor_http, token_a, dono, analise_a, publicar
    ):
        leitor, _ = _abrir(servidor_http, analise_a, token_a)
        mensagem = "linha1\nevent: etapa_concluida\ndata: {}\n\r\nlinha4\r"

        publicar(dono, analise_a, _evento(analise_a, mensagem=mensagem))
        publicar(dono, analise_a, _evento(analise_a, passo="sentinela"))

        quadro = leitor.proximo(5)
        assert quadro.evento == "passo_concluido"
        assert len(quadro.dados) == 1
        assert quadro.outras == []
        assert quadro.json["mensagem"] == mensagem
        seguinte = leitor.proximo(5)
        assert seguinte.evento == "passo_concluido"
        assert seguinte.json["passo"] == "sentinela"

    def test_unicode_atravessa_o_fluxo_sem_alteracao(
        self, servidor_http, token_a, dono, analise_a, publicar
    ):
        leitor, _ = _abrir(servidor_http, analise_a, token_a)
        mensagem = "ação concluída ✓ 日本語 😀"

        publicar(dono, analise_a, _evento(analise_a, "erro", codigo="INTERNO", mensagem=mensagem))

        assert leitor.proximo(5).json["mensagem"] == mensagem


class TestIsolamentoEDescarte:
    def test_eventos_de_outros_canais_nao_chegam_ao_fluxo(
        self, servidor_http, token_a, token_b, dono, outro_dono, analise_a, analise_b, publicar
    ):
        leitor_a, _ = _abrir(servidor_http, analise_a, token_a)
        leitor_b, _ = _abrir(servidor_http, analise_b, token_b)

        publicar(outro_dono, analise_b, _evento(analise_b, passo="so_do_b"))
        publicar(dono, analise_b, _evento(analise_b, passo="canal_de_a_analise_b"))
        publicar(outro_dono, analise_a, _evento(analise_a, passo="canal_de_b_analise_a"))
        publicar(dono, analise_a, _evento(analise_a, passo="so_do_a"))

        assert leitor_a.proximo(5).json["passo"] == "so_do_a"
        assert leitor_b.proximo(5).json["passo"] == "so_do_b"
        publicar(dono, analise_a, _evento(analise_a, passo="fim_a"))
        publicar(outro_dono, analise_b, _evento(analise_b, passo="fim_b"))
        assert leitor_a.proximo(5).json["passo"] == "fim_a"
        assert leitor_b.proximo(5).json["passo"] == "fim_b"

    def test_eventos_forjados_sao_descartados_e_o_fluxo_continua(
        self, servidor_http, token_a, dono, analise_a, publicar
    ):
        leitor, _ = _abrir(servidor_http, analise_a, token_a)
        base = {"tipo": "etapa_iniciada", "analise_id": str(analise_a)}
        forjados = [
            "isto não é json",
            "",
            "[]",
            "null",
            '"texto"',
            b"\xff\xfe\x00",
            json.dumps({**base, "extra": "x"}),
            json.dumps({**base, "analise_id": str(uuid.uuid4())}),
            json.dumps({**base, "tipo": "inventado"}),
            json.dumps({**base, "tipo": "etapa_iniciada\nevent: erro"}),
            json.dumps({**base, "progresso_etapa": 150}),
            json.dumps({**base, "progresso_etapa": "alto"}),
        ]

        for bruto in forjados:
            publicar(dono, analise_a, bruto)
        publicar(dono, analise_a, _evento(analise_a, passo="legitimo"))

        quadro = leitor.proximo(5)
        assert quadro.evento == "passo_concluido"
        assert quadro.json["passo"] == "legitimo"

    def test_nenhum_evento_entre_a_inscricao_e_o_estado_se_perde(
        self, servidor_http, token_a, dono, analise_a, motor_auth, redis_teste, publicar
    ):
        bloqueio = motor_auth.connect()
        try:
            bloqueio.execute(text("LOCK TABLE execucoes_etapa IN ACCESS EXCLUSIVE MODE"))
            leitor = servidor_http.abrir(analise_a, token_a)
            inscrito = esperar_ate(
                lambda: redis_teste.pubsub_numsub(canal(dono, analise_a))[0][1] >= 1, timeout=5
            )
            publicar(dono, analise_a, _evento(analise_a, passo="durante_o_snapshot"))
        finally:
            bloqueio.rollback()
            bloqueio.close()

        assert inscrito, "a inscrição deve ocorrer antes da leitura do estado"
        assert leitor.proximo(10).evento == "estado"
        quadro = leitor.proximo(5)
        assert quadro.json["passo"] == "durante_o_snapshot"


class TestEncerramento:
    def test_heartbeat_periodico_quando_nao_ha_eventos(
        self, servidor_http, token_a, analise_a, monkeypatch
    ):
        monkeypatch.setattr(settings, "SSE_HEARTBEAT_S", 0.3)
        leitor, _ = _abrir(servidor_http, analise_a, token_a)

        pings = [leitor.proximo(3) for _ in range(2)]

        for quadro in pings:
            assert quadro.comentarios == [": ping"]
            assert quadro.evento is None
            assert quadro.dados == []

    def test_evento_nao_e_confundido_com_heartbeat(
        self, servidor_http, token_a, dono, analise_a, publicar, monkeypatch
    ):
        monkeypatch.setattr(settings, "SSE_HEARTBEAT_S", 0.3)
        leitor, _ = _abrir(servidor_http, analise_a, token_a)

        publicar(dono, analise_a, _evento(analise_a, passo="entre_pings"))

        quadros = []
        while not quadros or quadros[-1].evento is None:
            quadros.append(leitor.proximo(3))
        assert quadros[-1].json["passo"] == "entre_pings"
        assert all(q.comentarios == [": ping"] for q in quadros[:-1])

    @pytest.mark.parametrize("via", ["logout", "chave_no_redis"])
    def test_revogacao_encerra_o_fluxo_em_ate_dois_heartbeats(
        self, servidor_http, token_a, analise_a, redis_teste, monkeypatch, via
    ):
        heartbeat = 0.4
        monkeypatch.setattr(settings, "SSE_HEARTBEAT_S", heartbeat)
        leitor, _ = _abrir(servidor_http, analise_a, token_a)

        if via == "logout":
            assert servidor_http.logout(token_a).status_code == 204
        else:
            redis_teste.set(f"revogado:{decodificar(token_a)['jti']}", 1, ex=60)
        inicio = time.monotonic()

        assert leitor.encerrou(2 * heartbeat + 1.5), "fluxo continuou aberto após a revogação"
        assert time.monotonic() - inicio < 2 * heartbeat + 1.5

    def test_token_que_expira_durante_o_fluxo_encerra(
        self, servidor_http, usuario_a, analise_a, monkeypatch
    ):
        monkeypatch.setattr(settings, "SSE_HEARTBEAT_S", 0.3)
        token = montar_token(usuario_a.id, expira_em=2)
        leitor, _ = _abrir(servidor_http, analise_a, token)

        assert leitor.encerrou(6), "fluxo continuou aberto após o vencimento do token"

    def test_falha_do_redis_na_revalidacao_encerra_o_fluxo(
        self, servidor_http, token_a, analise_a, monkeypatch
    ):
        heartbeat = 0.4
        monkeypatch.setattr(settings, "SSE_HEARTBEAT_S", heartbeat)
        leitor, _ = _abrir(servidor_http, analise_a, token_a)

        servidor_http.interruptor.set()

        assert leitor.encerrou(2 * heartbeat + 1.5), "falha do Redis não encerrou o fluxo"

    def test_duracao_maxima_encerra_o_fluxo(self, servidor_http, token_a, analise_a, monkeypatch):
        monkeypatch.setattr(settings, "SSE_HEARTBEAT_S", 0.3)
        monkeypatch.setattr(settings, "SSE_DURACAO_MAX_S", 1.0)
        inicio = time.monotonic()
        leitor, _ = _abrir(servidor_http, analise_a, token_a)

        leitor.ate_encerrar(timeout=6)

        assert 0.8 <= time.monotonic() - inicio < 5

    def test_estado_concluida_fecha_logo_apos_o_primeiro_quadro(
        self, servidor_http, token_a, analise_a, banco_pipeline
    ):
        banco_pipeline.definir_analise(analise_a, status="concluida", progresso=100)
        leitor = servidor_http.abrir(analise_a, token_a)
        assert leitor.aguardar_resposta() == 200

        quadro = leitor.proximo(5)

        assert quadro.evento == "estado"
        assert quadro.json["status"] == "concluida"
        assert leitor.encerrou(2), "fluxo de análise concluída deve fechar sozinho"


class TestRecursos:
    def test_conexao_do_banco_e_devolvida_antes_de_transmitir(
        self, servidor_http, token_a, analise_a, ambiente
    ):
        leitores = [_abrir(servidor_http, analise_a, token_a)[0] for _ in range(3)]

        livre = esperar_ate(lambda: ambiente.motor.pool.checkedout() == 0, timeout=1.0)

        assert livre, f"conexões em uso com o fluxo aberto: {ambiente.motor.pool.checkedout()}"
        assert not any(leitor.encerrou() for leitor in leitores)
