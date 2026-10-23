import datetime
import json
import logging
import time
import uuid

import pytest
import redis
from pydantic import ValidationError
from redis.backoff import NoBackoff
from redis.retry import Retry

from app.pipeline.eventos import EventoAnalise, PublicadorEventos, canal

USUARIO = uuid.UUID("11111111-1111-4111-8111-111111111111")
OUTRO_USUARIO = uuid.UUID("33333333-3333-4333-8333-333333333333")
ANALISE = uuid.UUID("44444444-4444-4444-8444-444444444444")
TIPOS = ["etapa_iniciada", "passo_concluido", "etapa_concluida", "etapa_pulada", "erro"]


def _evento(**campos) -> EventoAnalise:
    campos.setdefault("tipo", "etapa_iniciada")
    campos.setdefault("analise_id", ANALISE)
    return EventoAnalise(**campos)


def _assinar(cliente, nome_canal):
    assinante = cliente.pubsub()
    assinante.subscribe(nome_canal)
    confirmacao = assinante.get_message(timeout=3)
    assert confirmacao is not None
    assert confirmacao["type"] == "subscribe"
    return assinante


def _receber(assinante, limite_s=3.0):
    fim = time.monotonic() + limite_s
    while time.monotonic() < fim:
        mensagem = assinante.get_message(ignore_subscribe_messages=True, timeout=0.2)
        if mensagem is not None:
            return mensagem
    return None


@pytest.fixture
def redis_inalcancavel():
    cliente = redis.Redis(port=1, socket_connect_timeout=0.2, retry=Retry(NoBackoff(), 0))
    yield cliente
    cliente.close()


# canal


def test_canal_tem_formato_eventos_usuario_analise():
    assert canal(USUARIO, ANALISE) == f"eventos:{USUARIO}:{ANALISE}"


def test_canal_separa_usuarios_e_analises():
    outra_analise = uuid.uuid4()

    assert canal(USUARIO, ANALISE) != canal(OUTRO_USUARIO, ANALISE)
    assert canal(USUARIO, ANALISE) != canal(USUARIO, outra_analise)


# modelo


def test_valores_padrao():
    evento = _evento()

    assert evento.etapa is None
    assert evento.passo is None
    assert evento.progresso_etapa == 0
    assert evento.codigo is None
    assert evento.mensagem is None


def test_emitido_em_padrao_e_agora_em_utc_com_fuso():
    antes = datetime.datetime.now(datetime.UTC)

    evento = _evento()

    assert evento.emitido_em.tzinfo is not None
    assert evento.emitido_em.utcoffset() == datetime.timedelta(0)
    assert antes - datetime.timedelta(seconds=5) <= evento.emitido_em
    assert evento.emitido_em <= datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=5)


@pytest.mark.parametrize("tipo", TIPOS)
def test_tipos_aceitos(tipo):
    assert _evento(tipo=tipo).tipo == tipo


@pytest.mark.parametrize(
    "tipo", ["", "outro", "ERRO", "erro ", "etapa-iniciada", "event: erro", None, 1, ["erro"]]
)
def test_tipo_fora_do_conjunto_recusado(tipo):
    with pytest.raises(ValidationError):
        _evento(tipo=tipo)


@pytest.mark.parametrize("progresso", [0, 0.0, 12.5, 100, 100.0])
def test_progresso_dentro_da_faixa_aceito(progresso):
    assert _evento(progresso_etapa=progresso).progresso_etapa == progresso


@pytest.mark.parametrize(
    "progresso",
    [-0.1, -1, 100.1, 101, 1e9, float("nan"), float("inf"), float("-inf"), "abc", None],
)
def test_progresso_fora_da_faixa_ou_invalido_recusado(progresso):
    with pytest.raises(ValidationError):
        _evento(progresso_etapa=progresso)


def test_campo_extra_recusado():
    with pytest.raises(ValidationError):
        _evento(user_id=str(USUARIO))


@pytest.mark.parametrize(
    "campos",
    [
        {"analise_id": "nao-e-uuid"},
        {"analise_id": "../../etc"},
        {"analise_id": None},
        {"etapa": 5},
        {"passo": ["a"]},
        {"codigo": 3},
        {"mensagem": 1.5},
        {"emitido_em": "ontem"},
    ],
)
def test_tipos_invalidos_recusados(campos):
    with pytest.raises(ValidationError):
        _evento(**campos)


def test_evento_e_imutavel():
    evento = _evento()

    with pytest.raises(ValidationError):
        evento.tipo = "erro"
    with pytest.raises(ValidationError):
        evento.progresso_etapa = 50


# serialização


def test_to_json_e_json_valido_com_campos_esperados():
    evento = _evento(
        tipo="passo_concluido", etapa="sinais", passo="p1", progresso_etapa=33.3, mensagem="ok"
    )

    carga = json.loads(evento.to_json())

    assert carga["tipo"] == "passo_concluido"
    assert carga["analise_id"] == str(ANALISE)
    assert carga["etapa"] == "sinais"
    assert carga["passo"] == "p1"
    assert carga["progresso_etapa"] == 33.3
    assert carga["mensagem"] == "ok"
    assert carga["codigo"] is None
    assert datetime.datetime.fromisoformat(carga["emitido_em"]).utcoffset() is not None


def test_to_json_ida_e_volta():
    evento = _evento(tipo="erro", etapa="sinais", codigo="INTERNO", mensagem="Falha interna.")

    assert EventoAnalise.model_validate_json(evento.to_json()) == evento


@pytest.mark.parametrize(
    "mensagem",
    [
        "linha1\nlinha2",
        "linha1\r\nlinha2\rlinha3",
        'fecha"}\n\nevent: erro\ndata: {"tipo":"erro"}',
        "tab\tseparada",
        "ação 日本 😀",
        "x" * 200,
    ],
)
def test_to_json_fica_em_uma_linha_e_preserva_a_mensagem(mensagem):
    evento = _evento(mensagem=mensagem)

    texto = evento.to_json()

    assert "\n" not in texto
    assert "\r" not in texto
    assert json.loads(texto)["mensagem"] == mensagem
    assert EventoAnalise.model_validate_json(texto).mensagem == mensagem


def test_from_json_recusa_campo_extra_e_tipo_invalido():
    base = json.loads(_evento().to_json())

    with pytest.raises(ValidationError):
        EventoAnalise.model_validate_json(json.dumps({**base, "extra": 1}))
    with pytest.raises(ValidationError):
        EventoAnalise.model_validate_json(json.dumps({**base, "tipo": "inventado"}))
    with pytest.raises(ValidationError):
        EventoAnalise.model_validate_json(json.dumps({**base, "progresso_etapa": 150}))
    with pytest.raises(ValidationError):
        EventoAnalise.model_validate_json("{não é json")


# publicador


def test_publicar_entrega_o_json_no_canal_do_usuario_e_da_analise(redis_teste):
    evento = _evento(tipo="passo_concluido", etapa="sinais", passo="p1", progresso_etapa=50)
    assinante = _assinar(redis_teste, canal(USUARIO, ANALISE))
    try:
        resultado = PublicadorEventos(redis_teste).publicar(USUARIO, evento)
        mensagem = _receber(assinante)
    finally:
        assinante.close()

    assert resultado is None
    assert mensagem is not None
    assert mensagem["channel"] == canal(USUARIO, ANALISE).encode()
    assert mensagem["data"] == evento.to_json().encode()
    assert EventoAnalise.model_validate_json(mensagem["data"]) == evento


def test_publicar_nao_vaza_para_o_canal_de_outro_usuario(redis_teste):
    evento = _evento()
    alheio = _assinar(redis_teste, canal(OUTRO_USUARIO, ANALISE))
    proprio = _assinar(redis_teste, canal(USUARIO, ANALISE))
    try:
        PublicadorEventos(redis_teste).publicar(USUARIO, evento)
        recebida = _receber(proprio)
        vazada = _receber(alheio, limite_s=0.5)
    finally:
        alheio.close()
        proprio.close()

    assert recebida is not None
    assert vazada is None


def test_publicar_sem_assinante_nao_falha(redis_teste):
    PublicadorEventos(redis_teste).publicar(USUARIO, _evento())


def test_publicar_com_redis_fora_do_ar_nao_levanta_e_registra(
    redis_inalcancavel, texto_logs, caplog
):
    inicio = time.monotonic()

    PublicadorEventos(redis_inalcancavel).publicar(USUARIO, _evento())

    assert time.monotonic() - inicio < 2.0
    assert any(r.levelno >= logging.WARNING for r in caplog.records)
