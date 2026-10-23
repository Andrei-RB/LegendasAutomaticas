import datetime
import hashlib
import json
import re
from pathlib import Path

import pytest

from app.pipeline.hashing import calcular_hash_entrada, canonizar

HASH_A = "a" * 64
HASH_B = "b" * 64


def _hash(**sobrescritas):
    base = {
        "etapa": "sinais",
        "versao": 2,
        "entradas": {"ingestao": HASH_A},
        "parametros": {"idioma": "pt", "limite": 3},
    }
    base.update(sobrescritas)
    return calcular_hash_entrada(
        base["etapa"], base["versao"], base["entradas"], base["parametros"]
    )


# canonizar


def test_canonizar_ordena_chaves_e_remove_espacos():
    assert canonizar({"b": 1, "a": [1, 2], "c": {"z": None, "y": True}}) == (
        b'{"a":[1,2],"b":1,"c":{"y":true,"z":null}}'
    )


def test_canonizar_devolve_bytes():
    assert isinstance(canonizar({"a": 1}), bytes)


def test_canonizar_mantem_unicode_sem_escape():
    saida = canonizar({"titulo": "ação 日本 😀"})

    assert saida == '{"titulo":"ação 日本 😀"}'.encode()
    assert b"\\u" not in saida


def test_canonizar_independe_da_ordem_de_insercao():
    assert canonizar({"a": 1, "b": 2}) == canonizar({"b": 2, "a": 1})


def test_canonizar_preserva_ordem_das_listas():
    assert canonizar([1, 2, 3]) != canonizar([3, 2, 1])


@pytest.mark.parametrize(
    "valor",
    [
        {1, 2},
        b"bytes",
        Path("/dados/x"),
        datetime.datetime(2024, 1, 1, tzinfo=datetime.UTC),
        {"aninhado": {"conjunto": {"a"}}},
        {"lista": [object()]},
    ],
    ids=["set", "bytes", "path", "datetime", "set_aninhado", "objeto_em_lista"],
)
def test_canonizar_recusa_tipo_nao_json(valor):
    with pytest.raises(TypeError):
        canonizar(valor)


@pytest.mark.parametrize("valor", [float("nan"), float("inf"), float("-inf")])
def test_canonizar_recusa_nao_finitos(valor):
    with pytest.raises(ValueError):
        canonizar({"x": valor})


# calcular_hash_entrada


def test_hash_tem_64_hex_minusculos():
    assert re.fullmatch(r"[0-9a-f]{64}", _hash())


def test_hash_segue_formato_documentado():
    esperado = hashlib.sha256(
        canonizar(
            {
                "etapa": "sinais",
                "versao": 2,
                "entradas": {"ingestao": HASH_A},
                "parametros": {"idioma": "pt", "limite": 3},
            }
        )
    ).hexdigest()

    assert _hash() == esperado


def test_hash_valor_conhecido_regressao_do_formato():
    resultado = calcular_hash_entrada(
        "sinais", 2, {"ingestao": HASH_A}, {"idioma": "pt", "limite": 3, "titulo": "ação"}
    )

    assert resultado == "e182365079bf17008e4daebf3e8229383432b723c223823678e217f3a6164b05"


def test_hash_valor_conhecido_sem_entradas_e_parametro_nulo():
    assert calcular_hash_entrada("exemplo", 1, {}, {"semente": None}) == (
        "7fcece20c10fab0b2a124d333aeedfc5faecf1df72d692a052f8a85316d03501"
    )


def test_hash_e_deterministico():
    assert _hash() == _hash()


def test_hash_independe_da_ordem_das_chaves():
    um = calcular_hash_entrada("e", 1, {"a": HASH_A, "b": HASH_B}, {"x": 1, "y": {"p": 1, "q": 2}})
    dois = calcular_hash_entrada(
        "e", 1, {"b": HASH_B, "a": HASH_A}, {"y": {"q": 2, "p": 1}, "x": 1}
    )

    assert um == dois


@pytest.mark.parametrize(
    "alteracao",
    [
        {"etapa": "legendas"},
        {"versao": 3},
        {"entradas": {"ingestao": HASH_B}},
        {"entradas": {"outra": HASH_A}},
        {"entradas": {"ingestao": HASH_A, "extra": HASH_B}},
        {"entradas": {}},
        {"parametros": {"idioma": "en", "limite": 3}},
        {"parametros": {"idioma": "pt", "limite": 4}},
        {"parametros": {"idioma": "pt"}},
        {"parametros": {"idioma": "pt", "limite": 3, "novo": None}},
    ],
    ids=[
        "etapa",
        "versao",
        "valor_entrada",
        "nome_entrada",
        "entrada_extra",
        "sem_entradas",
        "valor_parametro",
        "valor_numerico",
        "parametro_removido",
        "parametro_nulo_adicionado",
    ],
)
def test_hash_muda_com_qualquer_componente(alteracao):
    assert _hash(**alteracao) != _hash()


@pytest.mark.parametrize(
    ("a", "b"),
    [(1, "1"), (True, 1), (False, 0), (None, "null"), (None, 0), ([1], "[1]"), (1, 1.0)],
    ids=[
        "int_str",
        "bool_int",
        "false_zero",
        "nulo_texto",
        "nulo_zero",
        "lista_texto",
        "int_float",
    ],
)
def test_hash_distingue_tipos_de_parametro(a, b):
    assert _hash(parametros={"p": a}) != _hash(parametros={"p": b})


def test_hash_ordem_de_lista_nos_parametros_importa():
    assert _hash(parametros={"p": [1, 2]}) != _hash(parametros={"p": [2, 1]})


def test_hash_entrada_e_parametro_com_mesmo_nome_nao_colidem():
    como_entrada = calcular_hash_entrada("e", 1, {"x": HASH_A}, {})
    como_parametro = calcular_hash_entrada("e", 1, {}, {"x": HASH_A})

    assert como_entrada != como_parametro


def test_hash_nao_ambiguo_entre_etapa_e_versao():
    assert calcular_hash_entrada("e1", 1, {}, {}) != calcular_hash_entrada("e", 11, {}, {})


def test_hash_com_unicode_nos_parametros():
    assert _hash(parametros={"titulo": "ação"}) != _hash(parametros={"titulo": "acao"})
    assert re.fullmatch(r"[0-9a-f]{64}", _hash(parametros={"titulo": "日本😀"}))


def test_hash_aceita_parametros_e_entradas_vazios():
    assert re.fullmatch(r"[0-9a-f]{64}", calcular_hash_entrada("e", 1, {}, {}))


def test_hash_nao_altera_os_mapeamentos_recebidos():
    entradas = {"b": HASH_B, "a": HASH_A}
    parametros = {"z": [3, 1], "a": {"y": 1, "x": 2}}
    copia = json.loads(json.dumps([entradas, parametros]))

    calcular_hash_entrada("e", 1, entradas, parametros)

    assert [entradas, parametros] == copia
    assert list(entradas) == ["b", "a"]


@pytest.mark.parametrize(
    "parametro",
    [{1, 2}, b"x", Path("/dados/x"), datetime.datetime(2024, 1, 1, tzinfo=datetime.UTC)],
    ids=["set", "bytes", "path", "datetime"],
)
def test_hash_recusa_parametro_nao_json(parametro):
    with pytest.raises(TypeError):
        calcular_hash_entrada("e", 1, {}, {"p": parametro})


@pytest.mark.parametrize("valor", [float("nan"), float("inf")])
def test_hash_recusa_parametro_nao_finito(valor):
    with pytest.raises(ValueError):
        calcular_hash_entrada("e", 1, {}, {"p": valor})
