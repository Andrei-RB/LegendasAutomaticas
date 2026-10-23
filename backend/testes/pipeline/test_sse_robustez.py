import json
import uuid

import pytest
from pydantic import ValidationError
from sqlalchemy import text

from app.nucleo.config import Settings, settings
from app.pipeline.eventos import EventoAnalise


def _evento(analise_id, tipo="passo_concluido", **campos) -> EventoAnalise:
    return EventoAnalise(tipo=tipo, analise_id=analise_id, **campos)


def _abrir(servidor, analise_id, token):
    leitor = servidor.abrir(analise_id, token)
    assert leitor.aguardar_resposta() == 200
    quadro = leitor.proximo()
    assert quadro.evento == "estado"
    return leitor, quadro


class TestEncerramentoPorEstado:
    def test_analise_falhou_fecha_logo_apos_o_primeiro_quadro(
        self, servidor_http, token_a, analise_a, banco_pipeline
    ):
        banco_pipeline.definir_analise(analise_a, status="falhou")
        leitor = servidor_http.abrir(analise_a, token_a)
        assert leitor.aguardar_resposta() == 200

        assert leitor.proximo(5).evento == "estado"
        assert leitor.encerrou(2), "fluxo de análise com falha deve fechar sozinho"

    def test_evento_de_erro_e_entregue_e_encerra_o_fluxo(
        self, servidor_http, token_a, dono, analise_a, publicar
    ):
        leitor, _ = _abrir(servidor_http, analise_a, token_a)

        publicar(
            dono,
            analise_a,
            _evento(analise_a, "erro", etapa="alfa", codigo="INTERNO", mensagem="Falha."),
        )

        quadro = leitor.proximo(5)
        assert quadro.evento == "erro"
        assert quadro.json["codigo"] == "INTERNO"
        assert leitor.encerrou(2)


class TestRevalidacaoDoUsuario:
    def test_usuario_desativado_encerra_o_fluxo(
        self, servidor_http, token_a, usuario_a, analise_a, motor_auth, monkeypatch
    ):
        monkeypatch.setattr(settings, "SSE_HEARTBEAT_S", 0.4)
        leitor, _ = _abrir(servidor_http, analise_a, token_a)

        with motor_auth.begin() as con:
            con.execute(
                text("UPDATE usuarios SET ativo = false WHERE id = :u"), {"u": usuario_a.id}
            )

        assert leitor.encerrou(3.5), "fluxo continuou aberto após a desativação do usuário"


class TestEventoGrande:
    def test_evento_acima_do_limite_e_descartado_e_o_fluxo_continua(
        self, servidor_http, token_a, dono, analise_a, publicar
    ):
        leitor, _ = _abrir(servidor_http, analise_a, token_a)
        enorme = json.dumps(
            {"tipo": "etapa_iniciada", "analise_id": str(analise_a), "mensagem": "x" * 10_000}
        )

        publicar(dono, analise_a, enorme)
        publicar(dono, analise_a, _evento(analise_a, passo="seguinte"))

        assert leitor.proximo(5).json["passo"] == "seguinte"


class TestModeloDoEvento:
    @pytest.mark.parametrize(
        "campos",
        [
            {"codigo": "INVENTADO"},
            {"codigo": "<script>"},
            {"etapa": "Etapa Com Espaço"},
            {"etapa": "a" * 100},
            {"passo": "../x"},
            {"mensagem": "x" * 201},
        ],
    )
    def test_campos_fora_do_formato_sao_recusados(self, campos):
        with pytest.raises(ValidationError):
            EventoAnalise(tipo="erro", analise_id=uuid.uuid4(), **campos)

    def test_codigo_do_catalogo_e_aceito(self):
        evento = EventoAnalise(tipo="erro", analise_id=uuid.uuid4(), codigo="GPU_INDISPONIVEL")

        assert evento.codigo == "GPU_INDISPONIVEL"


class TestLimitesDeConfiguracao:
    @pytest.mark.parametrize(
        "campo", ["SSE_HEARTBEAT_S", "SSE_DURACAO_MAX_S", "SSE_MAX_POR_USUARIO", "SSE_MAX_GLOBAL"]
    )
    @pytest.mark.parametrize("valor", [0, -1])
    def test_valores_nao_positivos_sao_recusados(self, campo, valor):
        with pytest.raises(ValidationError):
            Settings(**{campo: valor})
