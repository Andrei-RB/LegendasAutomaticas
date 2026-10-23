import logging
import re
import threading
import time

import pytest
import redis
from redis.backoff import NoBackoff
from redis.retry import Retry

from app.pipeline.trava_gpu import CHAVE_GPU, TravaGpu, TravaIndisponivel, TravaPerdida


class RedisQuebravel(redis.Redis):
    """Cliente real que passa a falhar com ConnectionError quando `quebrado` é verdadeiro."""

    quebrado = False

    def execute_command(self, *args, **opcoes):
        if self.quebrado:
            raise redis.exceptions.ConnectionError("conexão derrubada")
        return super().execute_command(*args, **opcoes)


@pytest.fixture
def redis_quebravel(url_redis_teste):
    cliente = RedisQuebravel.from_url(url_redis_teste)
    cliente.flushdb()
    yield cliente
    cliente.quebrado = False
    cliente.flushdb()
    cliente.close()


@pytest.fixture
def redis_inalcancavel():
    cliente = redis.Redis(port=1, socket_connect_timeout=0.2, retry=Retry(NoBackoff(), 0))
    yield cliente
    cliente.close()


@pytest.fixture
def travas():
    """Fábrica de travas; libera todas no fim para não deixar threads de renovação."""
    criadas = []

    def _criar(cliente, **opcoes):
        trava = TravaGpu(cliente, **opcoes)
        criadas.append(trava)
        return trava

    yield _criar
    for trava in criadas:
        trava.liberar()


def _aguardar(condicao, limite_s=3.0, passo_s=0.02):
    fim = time.monotonic() + limite_s
    while time.monotonic() < fim:
        if condicao():
            return True
        time.sleep(passo_s)
    return condicao()


def test_chave_padrao_e_gpu_lock():
    assert CHAVE_GPU == "gpu:lock"


def test_excecoes_sao_distintas():
    assert issubclass(TravaIndisponivel, Exception)
    assert issubclass(TravaPerdida, Exception)
    assert not issubclass(TravaPerdida, TravaIndisponivel)
    assert not issubclass(TravaIndisponivel, TravaPerdida)


# aquisição e liberação


def test_adquirir_grava_token_com_ttl_na_chave_padrao(redis_teste, travas):
    trava = travas(redis_teste, ttl_ms=5000, renovar=False)

    trava.adquirir()

    assert redis_teste.get(CHAVE_GPU) == trava.token.encode()
    assert 0 < redis_teste.pttl(CHAVE_GPU) <= 5000


def test_token_e_hex_de_32_caracteres_e_unico_por_instancia(redis_teste, travas):
    a = travas(redis_teste, renovar=False)
    b = travas(redis_teste, renovar=False, chave="gpu:outra")
    a.adquirir()
    b.adquirir()

    assert re.fullmatch(r"[0-9a-f]{32}", a.token)
    assert re.fullmatch(r"[0-9a-f]{32}", b.token)
    assert a.token != b.token


def test_chave_personalizada_nao_toca_a_padrao(redis_teste, travas):
    trava = travas(redis_teste, chave="gpu:teste", renovar=False)

    trava.adquirir()

    assert redis_teste.exists("gpu:teste") == 1
    assert redis_teste.exists(CHAVE_GPU) == 0


def test_liberar_remove_a_chave(redis_teste, travas):
    trava = travas(redis_teste, renovar=False)
    trava.adquirir()

    trava.liberar()

    assert redis_teste.exists(CHAVE_GPU) == 0


def test_liberar_e_idempotente(redis_teste, travas):
    trava = travas(redis_teste, renovar=False)
    trava.adquirir()

    trava.liberar()
    trava.liberar()

    assert redis_teste.exists(CHAVE_GPU) == 0


def test_liberar_sem_adquirir_nao_apaga_chave_alheia(redis_teste, travas):
    dona = travas(redis_teste, renovar=False)
    dona.adquirir()
    intrusa = travas(redis_teste, renovar=False)

    intrusa.liberar()

    assert redis_teste.get(CHAVE_GPU) == dona.token.encode()


def test_so_o_dono_libera(redis_teste, travas):
    trava = travas(redis_teste, renovar=False)
    trava.adquirir()
    redis_teste.set(CHAVE_GPU, "token-alheio")

    trava.liberar()

    assert redis_teste.get(CHAVE_GPU) == b"token-alheio"


def test_so_o_dono_libera_ao_sair_do_with(redis_teste, travas):
    trava = travas(redis_teste, renovar=False)

    with trava:
        redis_teste.set(CHAVE_GPU, "token-alheio")

    assert redis_teste.get(CHAVE_GPU) == b"token-alheio"


def test_with_adquire_e_libera(redis_teste, travas):
    trava = travas(redis_teste, renovar=False)

    with trava:
        assert redis_teste.get(CHAVE_GPU) == trava.token.encode()

    assert redis_teste.exists(CHAVE_GPU) == 0


def test_liberada_apos_excecao_no_corpo(redis_teste, travas):
    trava = travas(redis_teste, renovar=False)

    with pytest.raises(ValueError, match="falha no corpo"):
        with trava:
            raise ValueError("falha no corpo")

    assert redis_teste.exists(CHAVE_GPU) == 0


def test_outra_instancia_adquire_logo_apos_liberar(redis_teste, travas):
    primeira = travas(redis_teste, renovar=False)
    segunda = travas(redis_teste, renovar=False, espera_s=0.2)
    primeira.adquirir()
    primeira.liberar()

    segunda.adquirir()

    assert redis_teste.get(CHAVE_GPU) == segunda.token.encode()


# exclusão mútua e espera


def test_segunda_instancia_nao_adquire_enquanto_ocupada(redis_teste, travas):
    primeira = travas(redis_teste, renovar=False)
    segunda = travas(redis_teste, renovar=False, espera_s=0.3, intervalo_s=0.05)
    primeira.adquirir()

    inicio = time.monotonic()
    with pytest.raises(TravaIndisponivel):
        segunda.adquirir()
    decorrido = time.monotonic() - inicio

    assert 0.2 <= decorrido < 3.0
    assert redis_teste.get(CHAVE_GPU) == primeira.token.encode()


def test_with_na_segunda_instancia_levanta_e_nao_apaga_a_trava_da_primeira(redis_teste, travas):
    primeira = travas(redis_teste, renovar=False)
    segunda = travas(redis_teste, renovar=False, espera_s=0.1, intervalo_s=0.02)
    primeira.adquirir()

    with pytest.raises(TravaIndisponivel):
        with segunda:
            pytest.fail("não deveria entrar no corpo")

    assert redis_teste.get(CHAVE_GPU) == primeira.token.encode()


def test_espera_ate_a_liberacao(redis_teste, travas):
    primeira = travas(redis_teste, renovar=False)
    segunda = travas(redis_teste, renovar=False, espera_s=5.0, intervalo_s=0.02)
    primeira.adquirir()
    threading.Timer(0.3, primeira.liberar).start()

    inicio = time.monotonic()
    segunda.adquirir()
    decorrido = time.monotonic() - inicio

    assert 0.15 <= decorrido < 4.0
    assert redis_teste.get(CHAVE_GPU) == segunda.token.encode()


def test_duas_threads_nunca_estao_juntas_na_secao_critica(redis_teste):
    estado = {"ativos": 0, "maximo": 0, "entradas": 0}
    cadeado = threading.Lock()
    erros: list[BaseException] = []

    def laco():
        try:
            for _ in range(20):
                with TravaGpu(
                    redis_teste, ttl_ms=5000, espera_s=30.0, intervalo_s=0.005, renovar=False
                ):
                    with cadeado:
                        estado["ativos"] += 1
                        estado["entradas"] += 1
                        estado["maximo"] = max(estado["maximo"], estado["ativos"])
                    time.sleep(0.002)
                    with cadeado:
                        estado["ativos"] -= 1
        except BaseException as erro:
            erros.append(erro)

    threads = [threading.Thread(target=laco) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    assert erros == []
    assert estado["entradas"] == 40
    assert estado["maximo"] == 1
    assert redis_teste.exists(CHAVE_GPU) == 0


# TTL, renovação e perda


def test_trava_expira_por_ttl_quando_o_processo_morre(redis_teste, travas):
    morta = travas(redis_teste, ttl_ms=300, renovar=False)
    morta.adquirir()
    viva = travas(redis_teste, renovar=False, espera_s=5.0, intervalo_s=0.02)

    inicio = time.monotonic()
    viva.adquirir()

    assert time.monotonic() - inicio < 1.0
    assert redis_teste.get(CHAVE_GPU) == viva.token.encode()


def test_renovacao_mantem_a_trava_alem_do_ttl(redis_teste, travas):
    dona = travas(redis_teste, ttl_ms=300, renovar=True)
    dona.adquirir()
    fim = time.monotonic() + 1.2

    while time.monotonic() < fim:
        intrusa = TravaGpu(redis_teste, renovar=False, espera_s=0.05, intervalo_s=0.01)
        with pytest.raises(TravaIndisponivel):
            intrusa.adquirir()
        time.sleep(0.15)

    assert redis_teste.get(CHAVE_GPU) == dona.token.encode()
    assert dona.perdida is False
    dona.garantir()


def test_sem_renovacao_nao_cria_thread(redis_teste, travas):
    antes = set(threading.enumerate())
    trava = travas(redis_teste, renovar=False)

    trava.adquirir()

    assert set(threading.enumerate()) - antes == set()


def test_renovacao_cria_thread_e_liberar_a_encerra(redis_teste, travas):
    antes = set(threading.enumerate())
    trava = travas(redis_teste, ttl_ms=600, renovar=True)

    trava.adquirir()
    assert len(set(threading.enumerate()) - antes) >= 1
    trava.liberar()

    assert _aguardar(lambda: not (set(threading.enumerate()) - antes))


def test_perda_detectada_quando_a_chave_some(redis_teste, travas):
    trava = travas(redis_teste, ttl_ms=600, renovar=True)
    trava.adquirir()
    assert trava.perdida is False
    trava.garantir()

    redis_teste.delete(CHAVE_GPU)

    assert _aguardar(lambda: trava.perdida)
    with pytest.raises(TravaPerdida):
        trava.garantir()


def test_perda_detectada_quando_muda_de_dono_sem_sobrescrever(redis_teste, travas):
    trava = travas(redis_teste, ttl_ms=300, renovar=True)
    trava.adquirir()
    redis_teste.set(CHAVE_GPU, "novo-dono", px=100_000)

    assert _aguardar(lambda: trava.perdida)
    time.sleep(0.4)

    assert redis_teste.get(CHAVE_GPU) == b"novo-dono"
    assert redis_teste.pttl(CHAVE_GPU) > 50_000
    with pytest.raises(TravaPerdida):
        trava.garantir()


def test_liberar_apos_perda_nao_apaga_a_chave_do_novo_dono(redis_teste, travas):
    trava = travas(redis_teste, ttl_ms=300, renovar=True)
    trava.adquirir()
    redis_teste.set(CHAVE_GPU, "novo-dono", px=100_000)
    _aguardar(lambda: trava.perdida)

    trava.liberar()

    assert redis_teste.get(CHAVE_GPU) == b"novo-dono"


# Redis indisponível


def test_redis_inalcancavel_levanta_indisponivel_rapido(redis_inalcancavel, travas):
    trava = travas(redis_inalcancavel, espera_s=30.0, renovar=False)

    inicio = time.monotonic()
    with pytest.raises(TravaIndisponivel):
        trava.adquirir()

    assert time.monotonic() - inicio < 2.0


def test_with_com_redis_inalcancavel_nao_executa_o_corpo(redis_inalcancavel, travas):
    trava = travas(redis_inalcancavel, espera_s=30.0)
    executou = False

    inicio = time.monotonic()
    with pytest.raises(TravaIndisponivel):
        with trava:
            executou = True

    assert executou is False
    assert time.monotonic() - inicio < 2.0


def test_erro_do_redis_durante_adquirir_e_falha_fechada(redis_quebravel, travas):
    redis_quebravel.quebrado = True
    trava = travas(redis_quebravel, espera_s=30.0, renovar=False)

    inicio = time.monotonic()
    with pytest.raises(TravaIndisponivel):
        trava.adquirir()

    assert time.monotonic() - inicio < 2.0


def test_liberar_engole_erro_do_redis_e_registra_log(redis_quebravel, travas, texto_logs, caplog):
    trava = travas(redis_quebravel, renovar=False)
    trava.adquirir()
    redis_quebravel.quebrado = True

    trava.liberar()

    assert any(r.levelno >= logging.WARNING for r in caplog.records)


def test_erro_do_redis_ao_liberar_nao_mascara_excecao_do_corpo(redis_quebravel, travas):
    trava = travas(redis_quebravel, renovar=False)

    with pytest.raises(ValueError, match="do corpo"):
        with trava:
            redis_quebravel.quebrado = True
            raise ValueError("do corpo")
