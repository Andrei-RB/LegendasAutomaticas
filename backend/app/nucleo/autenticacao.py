import threading
import time
import unicodedata
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from redis import Redis

NOME_COOKIE = "viraliza_sessao"
ALGORITMO = "HS256"
CAMPOS_OBRIGATORIOS = ("exp", "iat", "jti", "sub")

SENHA_MINIMO = 12
SENHA_MAXIMO = 128

# Lista curta de senhas comuns com 12+ caracteres; complementa o tamanho mínimo.
SENHAS_COMUNS = frozenset(
    {
        "123456789012",
        "1234567890123",
        "12345678901234",
        "111111111111",
        "000000000000",
        "passwordpassword",
        "password1234",
        "password12345",
        "passw0rd1234",
        "qwertyuiopas",
        "qwertyuiop12",
        "qwertyuiopasdfgh",
        "abcdefghijkl",
        "abcdefghijklmnop",
        "iloveyou1234",
        "administrator",
        "senhasenhasenha",
        "senha1234567",
        "senha12345678",
        "minhasenha123",
        "mudar123456",
    }
)

_HASHER = PasswordHasher(time_cost=3, memory_cost=32768, parallelism=1)
# Limita hashes simultâneos para conter memória; sem vaga em 2 s a requisição é recusada.
_LIMITE_HASH = threading.BoundedSemaphore(4)
ESPERA_HASH_S = 2


class Sobrecarregado(Exception):
    pass


@contextmanager
def _vaga_de_hash() -> Iterator[None]:
    if not _LIMITE_HASH.acquire(timeout=ESPERA_HASH_S):
        raise Sobrecarregado
    try:
        yield
    finally:
        _LIMITE_HASH.release()


def _normalizar(senha: str) -> str:
    return unicodedata.normalize("NFKC", senha)


def hash_senha(senha: str) -> str:
    with _vaga_de_hash():
        return _HASHER.hash(_normalizar(senha))


def verificar_senha(hash_armazenado: str, senha: str) -> bool:
    try:
        with _vaga_de_hash():
            return _HASHER.verify(hash_armazenado, _normalizar(senha))
    except (VerificationError, InvalidHashError):
        return False


def precisa_novo_hash(hash_armazenado: str) -> bool:
    try:
        return _HASHER.check_needs_rehash(hash_armazenado)
    except InvalidHashError:
        return False


# Referência para igualar o tempo de login quando a conta não existe.
HASH_FALSO = hash_senha(uuid.uuid4().hex)


def validar_politica_senha(senha: str) -> None:
    texto = _normalizar(senha)
    if not SENHA_MINIMO <= len(texto) <= SENHA_MAXIMO:
        raise ValueError(f"A senha deve ter de {SENHA_MINIMO} a {SENHA_MAXIMO} caracteres.")
    if texto.casefold() in SENHAS_COMUNS:
        raise ValueError("Senha muito comum; escolha outra.")


class TokenInvalido(Exception):
    pass


@dataclass(frozen=True)
class SessaoToken:
    user_id: uuid.UUID
    jti: str
    expira_em: int


def emitir_token(user_id: uuid.UUID, segredo: str, minutos: int) -> tuple[str, SessaoToken]:
    agora = int(time.time())
    sessao = SessaoToken(user_id=user_id, jti=uuid.uuid4().hex, expira_em=agora + minutos * 60)
    carga = {"sub": str(user_id), "jti": sessao.jti, "iat": agora, "exp": sessao.expira_em}
    return jwt.encode(carga, segredo, algorithm=ALGORITMO), sessao


def validar_token(token: str, segredo: str) -> SessaoToken:
    try:
        carga = jwt.decode(
            token,
            segredo,
            algorithms=[ALGORITMO],
            options={"require": list(CAMPOS_OBRIGATORIOS)},
        )
        return SessaoToken(
            user_id=uuid.UUID(carga["sub"]), jti=str(carga["jti"]), expira_em=int(carga["exp"])
        )
    except (jwt.PyJWTError, ValueError, TypeError, KeyError) as erro:
        raise TokenInvalido from erro


def _chave_revogacao(jti: str) -> str:
    return f"revogado:{jti}"


def revogar(cliente: Redis, sessao: SessaoToken) -> None:
    ttl = max(1, sessao.expira_em - int(time.time()))
    cliente.set(_chave_revogacao(sessao.jti), 1, ex=ttl)


def esta_revogado(cliente: Redis, jti: str) -> bool:
    return bool(cliente.exists(_chave_revogacao(jti)))
