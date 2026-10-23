import threading
import uuid

import pytest

from app.api.v1.analises import conexoes_ativas
from app.nucleo.config import settings
from testes.pipeline.auxiliares import caminho_eventos, esperar_ate

ESPERA_LIBERACAO_S = 3.0


@pytest.fixture(autouse=True)
def configuracao(servidor_http, monkeypatch):
    """Heartbeat curto para detectar desconexões e contador global zerado no início."""
    monkeypatch.setattr(settings, "SSE_HEARTBEAT_S", 0.3)
    monkeypatch.setattr(settings, "SSE_MAX_POR_USUARIO", 5)
    monkeypatch.setattr(settings, "SSE_MAX_GLOBAL", 50)
    assert esperar_ate(lambda: conexoes_ativas() == 0, ESPERA_LIBERACAO_S), "contador sujo"


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


def _aberto(servidor, analise_id, token):
    leitor = servidor.abrir(analise_id, token)
    assert leitor.aguardar_resposta() == 200
    assert leitor.proximo().evento == "estado"
    return leitor


def _recusado(servidor, analise_id, token):
    leitor = servidor.abrir(analise_id, token)
    assert leitor.aguardar_resposta() == 429
    assert leitor.encerrou(3)
    espera = leitor.cabecalhos.get("retry-after", "")
    assert espera.isdigit(), f"Retry-After ausente ou inválido: {espera!r}"
    assert int(espera) > 0
    assert str(analise_id) not in leitor.corpo.decode("utf-8", errors="replace")
    return leitor


class TestLimites:
    def test_limite_por_usuario_responde_429_com_retry_after(
        self, servidor_http, token_a, analise_a, monkeypatch
    ):
        monkeypatch.setattr(settings, "SSE_MAX_POR_USUARIO", 2)
        abertos = [_aberto(servidor_http, analise_a, token_a) for _ in range(2)]

        _recusado(servidor_http, analise_a, token_a)

        assert conexoes_ativas() == 2
        abertos[0].fechar()
        assert esperar_ate(lambda: conexoes_ativas() == 1, ESPERA_LIBERACAO_S)
        _aberto(servidor_http, analise_a, token_a)
        assert conexoes_ativas() == 2

    def test_limite_de_um_usuario_nao_afeta_outro(
        self, servidor_http, token_a, token_b, analise_a, analise_b, monkeypatch
    ):
        monkeypatch.setattr(settings, "SSE_MAX_POR_USUARIO", 2)
        for _ in range(2):
            _aberto(servidor_http, analise_a, token_a)
        _recusado(servidor_http, analise_a, token_a)

        _aberto(servidor_http, analise_b, token_b)

        assert conexoes_ativas() == 3

    def test_limite_global_vale_para_todos_os_usuarios(
        self, servidor_http, token_a, token_b, analise_a, analise_b, monkeypatch
    ):
        monkeypatch.setattr(settings, "SSE_MAX_GLOBAL", 3)
        _aberto(servidor_http, analise_a, token_a)
        _aberto(servidor_http, analise_a, token_a)
        _aberto(servidor_http, analise_b, token_b)

        _recusado(servidor_http, analise_a, token_a)
        _recusado(servidor_http, analise_b, token_b)

        assert conexoes_ativas() == 3

    def test_limites_sao_lidos_a_cada_requisicao(
        self, servidor_http, token_a, analise_a, monkeypatch
    ):
        monkeypatch.setattr(settings, "SSE_MAX_POR_USUARIO", 1)
        _aberto(servidor_http, analise_a, token_a)
        _recusado(servidor_http, analise_a, token_a)

        monkeypatch.setattr(settings, "SSE_MAX_POR_USUARIO", 2)

        _aberto(servidor_http, analise_a, token_a)
        assert conexoes_ativas() == 2

    def test_rajada_de_aberturas_respeita_o_limite_exatamente(
        self, servidor_http, token_a, analise_a, monkeypatch
    ):
        monkeypatch.setattr(settings, "SSE_MAX_POR_USUARIO", 3)
        barreira = threading.Barrier(12)
        leitores = []
        trava = threading.Lock()

        def abrir():
            barreira.wait(timeout=30)
            leitor = servidor_http.abrir(analise_a, token_a)
            leitor.aguardar_resposta(10)
            with trava:
                leitores.append(leitor)

        fios = [threading.Thread(target=abrir, daemon=True) for _ in range(12)]
        for fio in fios:
            fio.start()
        for fio in fios:
            fio.join(timeout=60)

        status = sorted(leitor.status for leitor in leitores)
        assert status == [200] * 3 + [429] * 9
        assert conexoes_ativas() == 3


class TestLiberacao:
    @pytest.mark.parametrize("abrupto", [False, True], ids=["fecha", "reset"])
    def test_contador_volta_a_zero_apos_o_cliente_desconectar(
        self, servidor_http, token_a, analise_a, abrupto
    ):
        leitores = [_aberto(servidor_http, analise_a, token_a) for _ in range(3)]
        assert conexoes_ativas() == 3

        for leitor in leitores:
            leitor.fechar(abrupto=abrupto)

        assert esperar_ate(lambda: conexoes_ativas() == 0, ESPERA_LIBERACAO_S), (
            f"contador preso em {conexoes_ativas()}"
        )

    def test_encerramento_pelo_servidor_libera_a_vaga(
        self, servidor_http, token_a, analise_a, banco_pipeline
    ):
        banco_pipeline.definir_analise(analise_a, status="concluida")
        leitor = servidor_http.abrir(analise_a, token_a)
        assert leitor.aguardar_resposta() == 200
        assert leitor.encerrou(3)

        assert esperar_ate(lambda: conexoes_ativas() == 0, ESPERA_LIBERACAO_S)

    def test_revogacao_encerra_e_libera_a_vaga(self, servidor_http, token_a, analise_a):
        leitor = _aberto(servidor_http, analise_a, token_a)
        assert conexoes_ativas() == 1

        assert servidor_http.logout(token_a).status_code == 204

        assert leitor.encerrou(3)
        assert esperar_ate(lambda: conexoes_ativas() == 0, ESPERA_LIBERACAO_S)

    def test_requisicoes_recusadas_nao_consomem_vaga(
        self, servidor_http, token_a, analise_a, analise_b, monkeypatch
    ):
        monkeypatch.setattr(settings, "SSE_MAX_POR_USUARIO", 1)
        assert servidor_http.get(caminho_eventos(analise_a)).status_code == 401
        assert servidor_http.get(caminho_eventos(uuid.uuid4()), token_a).status_code == 404
        assert servidor_http.get(caminho_eventos(analise_b), token_a).status_code == 404
        assert servidor_http.get("/api/v1/analises/invalido/eventos", token_a).status_code == 422
        assert esperar_ate(lambda: conexoes_ativas() == 0, ESPERA_LIBERACAO_S)

        _aberto(servidor_http, analise_a, token_a)

        assert conexoes_ativas() == 1
