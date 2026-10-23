"""Utilidades dos testes do pipeline: etapas sintéticas, captura de eventos e leitor SSE."""

import contextlib
import hashlib
import json
import queue
import socket
import struct
import threading
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx
import redis
import redis.asyncio

from testes.auxiliares_auth import BASE_AUTH, cabecalho_cookie, token_da_resposta
from testes.conftest import ORIGEM_PERMITIDA


def esperar_ate(
    condicao: Callable[[], bool], timeout: float = 3.0, intervalo: float = 0.05
) -> bool:
    limite = time.monotonic() + timeout
    while time.monotonic() < limite:
        if condicao():
            return True
        time.sleep(intervalo)
    return bool(condicao())


def sha256_de(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()


class Chamadas:
    """Contadores thread-safe de execuções de passos e da concorrência máxima observada."""

    def __init__(self) -> None:
        self._trava = threading.Lock()
        self._contagem: Counter[str] = Counter()
        self._ativos = 0
        self.max_ativos = 0

    def entrar(self, chave: str) -> None:
        with self._trava:
            self._contagem[chave] += 1
            self._ativos += 1
            self.max_ativos = max(self.max_ativos, self._ativos)

    def sair(self) -> None:
        with self._trava:
            self._ativos -= 1

    def contar(self, chave: str) -> int:
        with self._trava:
            return self._contagem[chave]


class EtapaDeTeste:
    """Etapa sintética: cada passo grava um JSON determinístico; falhas são programáveis."""

    def __init__(
        self,
        nome: str = "alfa",
        *,
        versao: int = 1,
        fila: str = "cpu",
        n_passos: int = 3,
        parametros: tuple[str, ...] = (),
        entradas: tuple[str, ...] = (),
        usa_gpu: bool = False,
        limite_s: int = 3600,
        atraso_s: float = 0.0,
        chamadas: Chamadas | None = None,
        leituras_montante: tuple[str, ...] = (),
    ) -> None:
        from app.pipeline.executor import Etapa, Passo

        self.nome = nome
        self.chamadas = chamadas or Chamadas()
        self.atraso_s = atraso_s
        self.leituras_montante = leituras_montante
        self.n_passos = n_passos
        self.falhas: dict[str, Any] = {}
        self.comportamentos: dict[str, Callable[[Any], None]] = {}
        self.gancho: Callable[[Any, str], None] | None = None
        passos = tuple(
            Passo(nome=f"p{i}", saidas=(self.saida(i),), executar=self._fazer(i))
            for i in range(1, n_passos + 1)
        )
        self.etapa = Etapa(
            nome=nome,
            versao=versao,
            fila=fila,
            passos=passos,
            entradas=entradas,
            parametros=parametros,
            usa_gpu=usa_gpu,
            limite_s=limite_s,
        )

    def saida(self, indice: int) -> str:
        return f"{self.nome}_p{indice}.json"

    def contar(self, passo: str) -> int:
        return self.chamadas.contar(f"{self.nome}:{passo}")

    def contagens(self) -> dict[str, int]:
        return {f"p{i}": self.contar(f"p{i}") for i in range(1, self.n_passos + 1)}

    def _fazer(self, indice: int) -> Callable[[Any], None]:
        passo = f"p{indice}"

        def executar(ctx: Any) -> None:
            self.chamadas.entrar(f"{self.nome}:{passo}")
            try:
                if self.atraso_s:
                    time.sleep(self.atraso_s)
                if self.gancho is not None:
                    self.gancho(ctx, passo)
                falha = self.falhas.get(passo)
                if falha is not None:
                    raise falha() if not isinstance(falha, BaseException) else falha
                comportamento = self.comportamentos.get(passo)
                if comportamento is not None:
                    comportamento(ctx)
                    return
                self._corpo_padrao(ctx, indice)
            finally:
                self.chamadas.sair()

        return executar

    def _corpo_padrao(self, ctx: Any, indice: int) -> None:
        corpo: dict[str, Any] = {
            "etapa": self.nome,
            "passo": indice,
            "parametros": dict(ctx.parametros),
            "anterior": None,
        }
        if indice > 1:
            corpo["anterior"] = sha256_de(ctx.ler(self.saida(indice - 1)))
        else:
            corpo["montante"] = {n: sha256_de(ctx.ler(n)) for n in self.leituras_montante}
        ctx.gravar(self.saida(indice), json.dumps(corpo, sort_keys=True).encode("utf-8"))


def montar_registro(*etapas: Any) -> Any:
    from app.pipeline.executor import RegistroEtapas

    registro = RegistroEtapas()
    for item in etapas:
        registro.registrar(item.etapa if isinstance(item, EtapaDeTeste) else item)
    return registro


class Captura:
    """Assinante real de `eventos:*`; acumula (canal, evento) numa thread."""

    def __init__(self, url_redis: str) -> None:
        self._cliente = redis.Redis.from_url(url_redis)
        self._pubsub = self._cliente.pubsub()
        self._pubsub.psubscribe("eventos:*")
        self._trava = threading.Lock()
        self._itens: list[tuple[str, Any]] = []
        self._parar = threading.Event()
        confirmado = esperar_ate(self._confirmou, timeout=3.0, intervalo=0.01)
        assert confirmado, "assinatura de eventos não confirmada"
        self._thread = threading.Thread(target=self._coletar, daemon=True)
        self._thread.start()

    def _confirmou(self) -> bool:
        mensagem = self._pubsub.get_message(timeout=0.1)
        return bool(mensagem and mensagem["type"] == "psubscribe")

    def _coletar(self) -> None:
        while not self._parar.is_set():
            try:
                mensagem = self._pubsub.get_message(timeout=0.1)
            except redis.RedisError:
                return
            if not mensagem or mensagem["type"] != "pmessage":
                continue
            bruto = mensagem["data"].decode("utf-8")
            canal = mensagem["channel"].decode("utf-8")
            try:
                valor: Any = json.loads(bruto)
            except ValueError:
                valor = bruto
            with self._trava:
                self._itens.append((canal, valor))

    @property
    def itens(self) -> list[tuple[str, Any]]:
        with self._trava:
            return list(self._itens)

    @property
    def eventos(self) -> list[Any]:
        return [valor for _, valor in self.itens]

    def aguardar(self, quantidade: int, timeout: float = 5.0, assentar_s: float = 0.4) -> list[Any]:
        """Espera ao menos `quantidade` eventos e depois um intervalo para detectar excedentes."""
        esperar_ate(lambda: len(self.itens) >= quantidade, timeout)
        time.sleep(assentar_s)
        return self.eventos

    def encerrar(self) -> None:
        self._parar.set()
        self._thread.join(timeout=3)
        self._pubsub.close()
        self._cliente.close()


@dataclass
class Quadro:
    evento: str | None = None
    dados: list[str] = field(default_factory=list)
    comentarios: list[str] = field(default_factory=list)
    outras: list[str] = field(default_factory=list)

    @property
    def json(self) -> Any:
        return json.loads("\n".join(self.dados))


class FluxoEncerrado(AssertionError):
    pass


def _parsear_quadro(bloco: str) -> Quadro:
    quadro = Quadro()
    for linha in bloco.split("\n"):
        if linha.startswith(":"):
            quadro.comentarios.append(linha)
        elif linha.startswith("event:"):
            quadro.evento = linha[len("event:") :].removeprefix(" ")
        elif linha.startswith("data:"):
            quadro.dados.append(linha[len("data:") :].removeprefix(" "))
        else:
            quadro.outras.append(linha)
    return quadro


class LeitorSSE:
    """Cliente HTTP/1.1 mínimo em socket cru: lê o fluxo numa thread e fecha sob demanda."""

    def __init__(self, host: str, porta: int, caminho: str, cabecalhos: dict[str, str]) -> None:
        self.status: int | None = None
        self.cabecalhos: dict[str, str] = {}
        self.corpo = b""
        self._fila: queue.Queue[Quadro | None] = queue.Queue()
        self._encerrado = threading.Event()
        self._resposta = threading.Event()
        self._parar = threading.Event()
        self._abrupto = False
        self._chunked = False
        self._texto = b""
        self._sock = socket.create_connection((host, porta), timeout=5)
        self._sock.settimeout(0.2)
        linhas = [
            f"GET {caminho} HTTP/1.1",
            f"Host: {host}:{porta}",
            "Accept: text/event-stream",
            "Connection: close",
            *[f"{nome}: {valor}" for nome, valor in cabecalhos.items()],
            "",
            "",
        ]
        self._sock.sendall("\r\n".join(linhas).encode("ascii"))
        self._thread = threading.Thread(target=self._ler, daemon=True)
        self._thread.start()

    def _ler(self) -> None:
        buffer = bytearray()
        cabecalho_lido = False
        try:
            while not self._parar.is_set():
                try:
                    dados = self._sock.recv(65536)
                except TimeoutError:
                    continue
                except OSError:
                    break
                if not dados:
                    break
                buffer += dados
                if not cabecalho_lido:
                    fim = buffer.find(b"\r\n\r\n")
                    if fim < 0:
                        continue
                    self._interpretar_cabecalho(bytes(buffer[:fim]))
                    del buffer[: fim + 4]
                    cabecalho_lido = True
                if self._chunked:
                    if self._consumir_chunks(buffer):
                        break
                else:
                    self._receber(bytes(buffer))
                    buffer.clear()
        finally:
            self._finalizar()

    def _interpretar_cabecalho(self, bruto: bytes) -> None:
        linhas = bruto.decode("latin-1").split("\r\n")
        self.status = int(linhas[0].split(" ")[1])
        for linha in linhas[1:]:
            nome, _, valor = linha.partition(":")
            self.cabecalhos[nome.strip().lower()] = valor.strip()
        self._chunked = "chunked" in self.cabecalhos.get("transfer-encoding", "").lower()
        self._resposta.set()

    def _consumir_chunks(self, buffer: bytearray) -> bool:
        while True:
            fim_linha = buffer.find(b"\r\n")
            if fim_linha < 0:
                return False
            tamanho = int(bytes(buffer[:fim_linha]).split(b";")[0], 16)
            inicio = fim_linha + 2
            if tamanho == 0:
                return True
            if len(buffer) < inicio + tamanho + 2:
                return False
            self._receber(bytes(buffer[inicio : inicio + tamanho]))
            del buffer[: inicio + tamanho + 2]

    def _receber(self, dados: bytes) -> None:
        if self.status != 200 or "text/event-stream" not in self.cabecalhos.get("content-type", ""):
            self.corpo += dados
            return
        self._texto += dados
        while True:
            texto = self._texto.replace(b"\r\n", b"\n")
            fim = texto.find(b"\n\n")
            if fim < 0:
                self._texto = texto
                return
            bloco, self._texto = texto[:fim], texto[fim + 2 :]
            if bloco:
                self._fila.put(_parsear_quadro(bloco.decode("utf-8")))

    def _finalizar(self) -> None:
        with contextlib.suppress(OSError):
            if self._abrupto:
                self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
            self._sock.close()
        self._encerrado.set()
        self._resposta.set()
        self._fila.put(None)

    def aguardar_resposta(self, timeout: float = 5.0) -> int:
        if not self._resposta.wait(timeout) or self.status is None:
            raise AssertionError(f"sem resposta HTTP em {timeout}s")
        return self.status

    def proximo(self, timeout: float = 5.0) -> Quadro:
        try:
            item = self._fila.get(timeout=timeout)
        except queue.Empty:
            raise AssertionError(f"nenhum quadro em {timeout}s") from None
        if item is None:
            self._fila.put(None)
            raise FluxoEncerrado("fluxo encerrado pelo servidor")
        return item

    def ate_encerrar(self, timeout: float = 5.0) -> list[Quadro]:
        quadros: list[Quadro] = []
        limite = time.monotonic() + timeout
        while True:
            restante = max(0.05, limite - time.monotonic())
            try:
                quadros.append(self.proximo(restante))
            except FluxoEncerrado:
                return quadros

    def encerrou(self, timeout: float = 0.0) -> bool:
        return self._encerrado.wait(timeout)

    def fechar(self, abrupto: bool = False) -> None:
        self._abrupto = abrupto
        self._parar.set()
        self._thread.join(timeout=3)


class ClienteRedisInterruptivel(redis.Redis):
    """Cliente síncrono cuja chave `interruptor` faz todo comando falhar com ConnectionError."""

    interruptor: threading.Event

    def execute_command(self, *args: Any, **opcoes: Any) -> Any:
        if self.interruptor.is_set():
            raise redis.ConnectionError("redis indisponível (simulado)")
        return super().execute_command(*args, **opcoes)


class ClienteRedisAssincronoInterruptivel(redis.asyncio.Redis):
    """Equivalente assíncrono de ClienteRedisInterruptivel."""

    interruptor: threading.Event

    async def execute_command(self, *args: Any, **opcoes: Any) -> Any:
        if self.interruptor.is_set():
            raise redis.ConnectionError("redis indisponível (simulado)")
        return await super().execute_command(*args, **opcoes)


class Servidor:
    """Servidor uvicorn real em thread; cria leitores SSE e fecha todos no encerramento."""

    def __init__(self, porta: int, interruptor: threading.Event) -> None:
        self.host = "127.0.0.1"
        self.porta = porta
        self.interruptor = interruptor
        self.leitores: list[LeitorSSE] = []

    @property
    def base(self) -> str:
        return f"http://{self.host}:{self.porta}"

    def _cliente(self) -> httpx.Client:
        return httpx.Client(base_url=self.base, timeout=10, trust_env=False)

    def login(self, usuario: Any) -> str:
        with self._cliente() as cliente:
            resposta = cliente.post(
                f"{BASE_AUTH}/login",
                json={"email": usuario.email, "senha": usuario.senha},
                headers={"Origin": ORIGEM_PERMITIDA},
            )
        assert resposta.status_code == 200, resposta.text
        return token_da_resposta(resposta)

    def get(self, caminho: str, token: str | None = None) -> httpx.Response:
        cabecalhos = cabecalho_cookie(token) if token else {}
        with self._cliente() as cliente:
            return cliente.get(caminho, headers=cabecalhos)

    def post(self, caminho: str, token: str | None = None, **corpo: Any) -> httpx.Response:
        cabecalhos = {"Origin": ORIGEM_PERMITIDA, **(cabecalho_cookie(token) if token else {})}
        with self._cliente() as cliente:
            return cliente.post(caminho, headers=cabecalhos, **corpo)

    def logout(self, token: str) -> httpx.Response:
        return self.post(f"{BASE_AUTH}/logout", token)

    def abrir(self, analise_id: Any, token: str | None = None) -> LeitorSSE:
        cabecalhos = cabecalho_cookie(token) if token else {}
        leitor = LeitorSSE(self.host, self.porta, caminho_eventos(analise_id), cabecalhos)
        self.leitores.append(leitor)
        return leitor

    def fechar_leitores(self) -> None:
        for leitor in self.leitores:
            leitor.fechar()
        self.leitores.clear()


def caminho_eventos(analise_id: Any) -> str:
    return f"/api/v1/analises/{analise_id}/eventos"
