import contextlib
import hashlib
import os
import re
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

SEGMENTO = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
MAX_SEGMENTOS = 3
TAMANHO_BLOCO = 1024 * 1024
LIMITE_LEITURA_BYTES = 64 * 1024 * 1024
MODO_DIRETORIO = 0o700
MODO_ARQUIVO = 0o600


class ErroArmazenamento(Exception):
    pass


class CaminhoInvalido(ErroArmazenamento):
    pass


@dataclass(frozen=True)
class ArtefatoGravado:
    nome: str
    sha256: str
    bytes: int


@dataclass
class GravacaoAtomica:
    caminho: Path
    artefato: ArtefatoGravado | None = field(default=None)


class Armazenamento(Protocol):
    def gravar(
        self, user_id: uuid.UUID, video_id: uuid.UUID, nome: str, dados: bytes
    ) -> ArtefatoGravado: ...

    def gravacao_atomica(
        self, user_id: uuid.UUID, video_id: uuid.UUID, nome: str
    ) -> contextlib.AbstractContextManager[GravacaoAtomica]: ...

    def ler(self, user_id: uuid.UUID, video_id: uuid.UUID, nome: str) -> bytes: ...

    def caminho(self, user_id: uuid.UUID, video_id: uuid.UUID, nome: str) -> Path: ...

    def existe(self, user_id: uuid.UUID, video_id: uuid.UUID, nome: str) -> bool: ...

    def remover(self, user_id: uuid.UUID, video_id: uuid.UUID, nome: str) -> None: ...

    def verificar(
        self, user_id: uuid.UUID, video_id: uuid.UUID, nome: str, sha256: str
    ) -> bool: ...


def sha256_arquivo(caminho: Path) -> tuple[str, int]:
    resumo = hashlib.sha256()
    total = 0
    with open(caminho, "rb") as arquivo:
        while bloco := arquivo.read(TAMANHO_BLOCO):
            resumo.update(bloco)
            total += len(bloco)
    return resumo.hexdigest(), total


def _validar_nome(nome: str) -> tuple[str, ...]:
    if not isinstance(nome, str):
        raise CaminhoInvalido("nome inválido")
    segmentos = tuple(nome.split("/"))
    if len(segmentos) > MAX_SEGMENTOS or not all(SEGMENTO.fullmatch(s) for s in segmentos):
        raise CaminhoInvalido("nome inválido")
    return segmentos


def _validar_id(valor: object) -> str:
    if not isinstance(valor, uuid.UUID):
        raise CaminhoInvalido("identificador inválido")
    return str(valor)


class ArmazenamentoLocal:
    """Grava artefatos em `<raiz>/<user_id>/<video_id>/<nome>`, sem seguir links simbólicos."""

    def __init__(self, raiz: Path) -> None:
        self.raiz = Path(raiz)
        self._raiz_real: Path | None = None

    def _resolver(
        self, user_id: uuid.UUID, video_id: uuid.UUID, nome: str, *, criar_raiz: bool = False
    ) -> Path:
        partes = (_validar_id(user_id), _validar_id(video_id), *_validar_nome(nome))
        raiz_real = self._raiz_resolvida(criar=criar_raiz)
        destino = raiz_real.joinpath(*partes)
        # Qualquer componente existente que seja link ou junção é recusado.
        atual = raiz_real
        for parte in partes:
            atual = atual / parte
            if atual.is_symlink() or atual.is_junction():
                raise CaminhoInvalido("caminho inválido")
        return destino

    def _raiz_resolvida(self, *, criar: bool) -> Path:
        """Fixa o caminho real da raiz na primeira vez em que ela existe."""
        if self._raiz_real is None:
            if criar:
                self.raiz.mkdir(mode=MODO_DIRETORIO, parents=True, exist_ok=True)
            resolvida = Path(os.path.realpath(self.raiz))
            if not self.raiz.exists():
                return resolvida
            self._raiz_real = resolvida
        return self._raiz_real

    def caminho(self, user_id: uuid.UUID, video_id: uuid.UUID, nome: str) -> Path:
        return self._resolver(user_id, video_id, nome)

    def existe(self, user_id: uuid.UUID, video_id: uuid.UUID, nome: str) -> bool:
        return self._resolver(user_id, video_id, nome).is_file()

    def ler(self, user_id: uuid.UUID, video_id: uuid.UUID, nome: str) -> bytes:
        destino = self._resolver(user_id, video_id, nome)
        try:
            if destino.stat().st_size > LIMITE_LEITURA_BYTES:
                raise ErroArmazenamento("artefato grande demais para leitura em memória")
            return destino.read_bytes()
        except OSError as erro:
            raise ErroArmazenamento("falha ao ler o artefato") from erro

    def remover(self, user_id: uuid.UUID, video_id: uuid.UUID, nome: str) -> None:
        destino = self._resolver(user_id, video_id, nome)
        try:
            destino.unlink(missing_ok=True)
        except OSError as erro:
            raise ErroArmazenamento("falha ao remover o artefato") from erro

    def verificar(self, user_id: uuid.UUID, video_id: uuid.UUID, nome: str, sha256: str) -> bool:
        destino = self._resolver(user_id, video_id, nome)
        if not destino.is_file():
            return False
        return sha256_arquivo(destino)[0] == sha256

    def gravar(
        self, user_id: uuid.UUID, video_id: uuid.UUID, nome: str, dados: bytes
    ) -> ArtefatoGravado:
        with self.gravacao_atomica(user_id, video_id, nome) as gravacao:
            with open(gravacao.caminho, "wb") as arquivo:
                arquivo.write(dados)
        if gravacao.artefato is None:
            raise ErroArmazenamento("gravação não concluída")
        return gravacao.artefato

    @contextmanager
    def gravacao_atomica(
        self, user_id: uuid.UUID, video_id: uuid.UUID, nome: str
    ) -> Iterator[GravacaoAtomica]:
        destino = self._resolver(user_id, video_id, nome, criar_raiz=True)
        pasta = destino.parent
        self._criar_pastas(pasta)
        temporario = pasta / f".{destino.name}.{uuid.uuid4().hex[:8]}.tmp"
        gravacao = GravacaoAtomica(caminho=temporario)
        try:
            yield gravacao
            if not temporario.is_file():
                raise ErroArmazenamento("artefato não foi produzido")
            self._sincronizar(temporario)
            os.chmod(temporario, MODO_ARQUIVO)
            sha256, tamanho = sha256_arquivo(temporario)
            os.replace(temporario, destino)
            gravacao.artefato = ArtefatoGravado(nome=nome, sha256=sha256, bytes=tamanho)
        finally:
            with contextlib.suppress(FileNotFoundError):
                temporario.unlink()

    def _criar_pastas(self, pasta: Path) -> None:
        raiz_real = self._raiz_resolvida(criar=True)
        atual = raiz_real
        for parte in pasta.relative_to(raiz_real).parts:
            atual = atual / parte
            atual.mkdir(mode=MODO_DIRETORIO, exist_ok=True)

    @staticmethod
    def _sincronizar(caminho: Path) -> None:
        with open(caminho, "rb+") as arquivo:
            os.fsync(arquivo.fileno())
