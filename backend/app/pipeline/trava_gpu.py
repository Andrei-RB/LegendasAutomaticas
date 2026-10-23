import secrets
import threading
import time
from types import TracebackType

from redis import Redis
from redis.exceptions import RedisError

from app.nucleo.logger import logger

CHAVE_GPU = "gpu:lock"

_LIBERAR = (
    "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) end return 0"
)
_RENOVAR = (
    "if redis.call('get', KEYS[1]) == ARGV[1] then "
    "return redis.call('pexpire', KEYS[1], ARGV[2]) end return 0"
)


class TravaIndisponivel(Exception):
    pass


class TravaPerdida(Exception):
    pass


class TravaGpu:
    """Trava exclusiva da GPU no Redis: dono identificado por token, TTL e renovação periódica."""

    def __init__(
        self,
        redis: Redis,
        *,
        ttl_ms: int = 60_000,
        espera_s: float = 600.0,
        intervalo_s: float = 0.25,
        renovar: bool = True,
        chave: str = CHAVE_GPU,
    ) -> None:
        self._redis = redis
        self._ttl_ms = ttl_ms
        self._espera_s = espera_s
        self._intervalo_s = intervalo_s
        self._renovar = renovar
        self._chave = chave
        self.token: str | None = None
        self._perdida = threading.Event()
        self._parar = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def perdida(self) -> bool:
        return self._perdida.is_set()

    def garantir(self) -> None:
        if self.perdida:
            raise TravaPerdida("trava da GPU perdida")

    def adquirir(self) -> None:
        token = secrets.token_hex(16)
        limite = time.monotonic() + self._espera_s
        while True:
            try:
                obtida = self._redis.set(self._chave, token, nx=True, px=self._ttl_ms)
            except RedisError as erro:
                # Sem o Redis não há exclusão mútua: nenhum trabalho de GPU pode começar.
                raise TravaIndisponivel("Redis indisponível") from erro
            if obtida:
                break
            if time.monotonic() >= limite:
                raise TravaIndisponivel("GPU ocupada")
            time.sleep(min(self._intervalo_s, max(0.0, limite - time.monotonic())))
        self.token = token
        self._perdida.clear()
        self._parar.clear()
        if self._renovar:
            self._thread = threading.Thread(
                target=self._renovar_periodicamente, name="renovacao-gpu-lock", daemon=True
            )
            self._thread.start()

    def liberar(self) -> None:
        token, self.token = self.token, None
        if token is None:
            return
        self._parar.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
        try:
            self._redis.eval(_LIBERAR, 1, self._chave, token)
        except RedisError as erro:
            # O TTL libera a trava; a falha só é registrada.
            logger.warning(f"Falha ao liberar a trava da GPU: {type(erro).__name__}")

    def _renovar_periodicamente(self) -> None:
        token = self.token
        ttl_s = self._ttl_ms / 1000
        ultima = time.monotonic()
        while not self._parar.wait(self._ttl_ms / 3000):
            try:
                mantida = self._redis.eval(_RENOVAR, 1, self._chave, token, self._ttl_ms)
            except RedisError as erro:
                logger.warning(f"Falha ao renovar a trava da GPU: {type(erro).__name__}")
                if time.monotonic() - ultima >= ttl_s:
                    self._perdida.set()
                    return
                continue
            if not mantida:
                self._perdida.set()
                logger.error("Trava da GPU perdida: a chave expirou ou mudou de dono.")
                return
            ultima = time.monotonic()

    def __enter__(self) -> "TravaGpu":
        self.adquirir()
        return self

    def __exit__(
        self,
        tipo: type[BaseException] | None,
        erro: BaseException | None,
        rastreio: TracebackType | None,
    ) -> None:
        self.liberar()
