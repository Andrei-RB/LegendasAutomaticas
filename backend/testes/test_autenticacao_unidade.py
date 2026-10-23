import importlib
import re

import pytest

SENHA = "uma-senha-longa-e-boa"


def _aut():
    return importlib.import_module("app.nucleo.autenticacao")


def test_hash_tem_prefixo_argon2id():
    assert _aut().hash_senha(SENHA).startswith("$argon2id$")


def test_hash_nao_contem_a_senha():
    assert SENHA not in _aut().hash_senha(SENHA)


def test_hash_usa_parametros_minimos_recomendados():
    memoria, tempo = re.search(r"m=(\d+),t=(\d+)", _aut().hash_senha(SENHA)).groups()

    assert int(memoria) >= 19456
    assert int(tempo) >= 2


def test_hash_com_sal_aleatorio_difere_para_a_mesma_senha():
    assert _aut().hash_senha(SENHA) != _aut().hash_senha(SENHA)


def test_round_trip_verifica_senha_correta():
    assert _aut().verificar_senha(_aut().hash_senha(SENHA), SENHA) is True


def test_verifica_senha_errada_retorna_false():
    assert _aut().verificar_senha(_aut().hash_senha(SENHA), SENHA + "x") is False


def test_verifica_senha_vazia_retorna_false():
    assert _aut().verificar_senha(_aut().hash_senha(SENHA), "") is False


def test_round_trip_com_unicode():
    senha = "açúcar-ñandú-日本語-🔒"

    assert _aut().verificar_senha(_aut().hash_senha(senha), senha) is True


@pytest.mark.parametrize(
    "hash_invalido",
    ["", "lixo", "$argon2id$", "$argon2id$v=19$m=1,t=1,p=1$x$y", "$2b$12$abc", " " * 10],
)
def test_hash_malformado_retorna_false_sem_excecao(hash_invalido):
    assert _aut().verificar_senha(hash_invalido, SENHA) is False


@pytest.mark.parametrize("senha", ["a" * 12, "a" * 128, "é" * 12, "é" * 128])
def test_politica_aceita_entre_12_e_128_caracteres(senha):
    _aut().validar_politica_senha(senha)


@pytest.mark.parametrize("senha", ["", "a" * 11, "é" * 11, "a" * 129, "é" * 129])
def test_politica_recusa_fora_do_intervalo(senha):
    with pytest.raises(ValueError):
        _aut().validar_politica_senha(senha)


@pytest.mark.parametrize("senha", ["123456789012", "passwordpassword"])
def test_politica_recusa_senhas_comuns(senha):
    assert len(senha) >= 12
    with pytest.raises(ValueError):
        _aut().validar_politica_senha(senha)


@pytest.mark.parametrize(
    "senha",
    [
        "açúcar-ñandú-日本語",
        "frase com espaços no meio",
        "  espaços nas pontas  ",
        "somenteletrasminusculas",
        "SOMENTELETRASMAIUSCULAS",
        "9" * 7 + "8" * 6,
    ],
)
def test_politica_sem_regra_de_composicao(senha):
    assert len(senha) >= 12
    _aut().validar_politica_senha(senha)


def test_politica_conta_caracteres_e_nao_bytes():
    senha = "日" * 12

    assert len(senha.encode()) > 12
    _aut().validar_politica_senha(senha)
