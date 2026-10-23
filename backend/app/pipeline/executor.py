import contextlib
import hashlib
import re
import time
import traceback
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from redis import Redis
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as inserir
from sqlalchemy.orm import Session, sessionmaker

from app.modelos.analise import Analise, ExecucaoEtapa
from app.nucleo.logger import logger
from app.pipeline.armazenamento import Armazenamento, GravacaoAtomica, sha256_arquivo
from app.pipeline.erros import ErroPipeline, traduzir
from app.pipeline.eventos import EventoAnalise, PublicadorEventos, TipoEvento
from app.pipeline.hashing import calcular_hash_entrada, canonizar
from app.pipeline.trava_gpu import TravaGpu

Fila = Literal["gpu", "cpu", "ai", "render"]
FILAS = ("gpu", "cpu", "ai", "render")
NOME_VALIDO = re.compile(r"[a-z][a-z0-9_]{0,31}")
NOME_SAIDA = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
# Abaixo do visibility_timeout do broker (7500 s), descontados o lease extra e a folga do Celery.
LIMITE_MAX_ETAPA_S = 7000


def _nome_fisico(analise_id: uuid.UUID, nome: str) -> str:
    """Os arquivos de cada análise ficam em pasta própria, mesmo quando o vídeo é o mesmo."""
    return f"{analise_id}/{nome}"


class ContextoPasso:
    """Acesso de um passo aos dados da análise; só as saídas declaradas podem ser gravadas."""

    def __init__(
        self,
        *,
        user_id: uuid.UUID,
        video_id: uuid.UUID,
        analise_id: uuid.UUID,
        parametros: Mapping[str, Any],
        armazenamento: Armazenamento,
        saidas: tuple[str, ...],
        trava: TravaGpu | None,
    ) -> None:
        self.user_id = user_id
        self.video_id = video_id
        self.analise_id = analise_id
        self.parametros = parametros
        self._armazenamento = armazenamento
        self._saidas = frozenset(saidas)
        self._trava = trava

    def _exigir_saida(self, nome: str) -> None:
        if nome not in self._saidas:
            raise ErroPipeline("INTERNO", f"saída não declarada: {nome!r}")

    def ler(self, nome: str) -> bytes:
        return self._armazenamento.ler(
            self.user_id, self.video_id, _nome_fisico(self.analise_id, nome)
        )

    def caminho(self, nome: str) -> Path:
        return self._armazenamento.caminho(
            self.user_id, self.video_id, _nome_fisico(self.analise_id, nome)
        )

    def gravar(self, nome: str, dados: bytes) -> None:
        self._exigir_saida(nome)
        self._armazenamento.gravar(
            self.user_id, self.video_id, _nome_fisico(self.analise_id, nome), dados
        )

    def gravacao_atomica(self, nome: str) -> contextlib.AbstractContextManager[GravacaoAtomica]:
        self._exigir_saida(nome)
        return self._armazenamento.gravacao_atomica(
            self.user_id, self.video_id, _nome_fisico(self.analise_id, nome)
        )

    def verificar_trava(self) -> None:
        """Os passos longos devem chamar este método: a perda da trava só é vista aqui."""
        if self._trava is not None:
            self._trava.garantir()


@dataclass(frozen=True)
class Passo:
    nome: str
    saidas: tuple[str, ...]
    executar: Callable[[ContextoPasso], None]


@dataclass(frozen=True)
class Etapa:
    nome: str
    versao: int
    fila: Fila
    passos: tuple[Passo, ...]
    entradas: tuple[str, ...] = ()
    parametros: tuple[str, ...] = ()
    usa_gpu: bool = False
    limite_s: int = 3600

    def __post_init__(self) -> None:
        nomes_passos = [p.nome for p in self.passos]
        valido = (
            NOME_VALIDO.fullmatch(self.nome)
            and self.fila in FILAS
            and self.passos
            and len(set(nomes_passos)) == len(nomes_passos)
            and all(NOME_VALIDO.fullmatch(n) for n in nomes_passos)
            and all(NOME_SAIDA.fullmatch(s) for p in self.passos for s in p.saidas)
            and all(NOME_VALIDO.fullmatch(e) for e in self.entradas)
            and 0 < self.limite_s <= LIMITE_MAX_ETAPA_S
        )
        if not valido:
            raise ValueError("definição de etapa inválida")


class RegistroEtapas:
    def __init__(self) -> None:
        self._etapas: dict[str, Etapa] = {}

    def registrar(self, etapa: Etapa) -> None:
        if etapa.nome in self._etapas:
            raise ValueError("etapa já registrada")
        # Saídas com o mesmo nome fariam uma etapa apagar ou sobrescrever os arquivos de outra.
        existentes = {s for e in self._etapas.values() for p in e.passos for s in p.saidas}
        if existentes.intersection(s for p in etapa.passos for s in p.saidas):
            raise ValueError("saída já declarada por outra etapa")
        self._etapas[etapa.nome] = etapa

    def obter(self, nome: str) -> Etapa:
        etapa = self._etapas.get(nome) if isinstance(nome, str) else None
        if etapa is None:
            raise ErroPipeline("ETAPA_DESCONHECIDA", f"etapa {str(nome)[:64]!r}")
        return etapa

    def __contains__(self, nome: object) -> bool:
        return isinstance(nome, str) and nome in self._etapas


@dataclass(frozen=True)
class ResultadoEtapa:
    status: Literal["concluida", "pulada", "em_execucao"]
    hash_entrada: str
    passos_executados: tuple[str, ...]
    passos_reaproveitados: tuple[str, ...]
    lease_restante_s: float = 0.0


@dataclass
class _Execucao:
    id: uuid.UUID
    iniciado_em: datetime
    artefatos: dict[str, Any]
    metricas: dict[str, Any]


def _hash_artefatos(arquivos: list[dict[str, Any]]) -> str:
    return hashlib.sha256(canonizar({a["nome"]: a["sha256"] for a in arquivos})).hexdigest()


class ExecutorPipeline:
    def __init__(
        self,
        fabrica_sessao: sessionmaker[Session],
        redis: Redis,
        armazenamento: Armazenamento,
        registro: RegistroEtapas,
        *,
        lease_extra_s: int = 300,
        trava_ttl_ms: int = 60_000,
        trava_espera_s: float = 600.0,
    ) -> None:
        self._fabrica = fabrica_sessao
        self._redis = redis
        self._armazenamento = armazenamento
        self._registro = registro
        self._lease_extra_s = lease_extra_s
        self._trava_ttl_ms = trava_ttl_ms
        self._trava_espera_s = trava_espera_s
        self._eventos = PublicadorEventos(redis)

    def executar(self, analise_id: uuid.UUID, user_id: uuid.UUID, etapa: str) -> ResultadoEtapa:
        definicao = self._registro.obter(etapa)
        with self._fabrica() as sessao:
            analise = sessao.scalar(
                select(Analise).where(Analise.id == analise_id, Analise.user_id == user_id)
            )
            sessao.commit()
        if analise is None:
            raise ErroPipeline("ANALISE_INEXISTENTE")
        video_id = analise.video_id
        parametros = {k: (analise.parametros or {}).get(k) for k in definicao.parametros}
        try:
            entradas = self._hashes_das_entradas(definicao, analise_id, user_id, video_id)
        except Exception as erro:
            publico = traduzir(erro)
            detalhe = erro.detalhe if isinstance(erro, ErroPipeline) else str(erro)
            falha = ErroPipeline(publico.codigo, detalhe)
            self._registrar_falha_previa(definicao, analise_id, user_id, erro, falha)
            raise falha from erro
        hash_entrada = calcular_hash_entrada(definicao.nome, definicao.versao, entradas, parametros)

        execucao = self._reivindicar(definicao, analise_id, user_id, video_id, hash_entrada)
        if execucao is None:
            return self._resultado_sem_execucao(definicao, analise_id, user_id, hash_entrada)

        executados: list[str] = []
        reaproveitados: list[str] = []
        try:
            self._marcar_analise(analise_id, user_id, status="processando", etapa=definicao.nome)
            self._emitir(user_id, "etapa_iniciada", analise_id, definicao)
            self._rodar_passos(
                definicao,
                execucao,
                analise_id,
                user_id,
                video_id,
                parametros,
                executados,
                reaproveitados,
            )
            self._concluir(execucao)
        except BaseException as erro:
            self._registrar_falha(definicao, execucao, analise_id, user_id, erro)
            if not isinstance(erro, Exception):
                raise
            publico = traduzir(erro)
            detalhe = erro.detalhe if isinstance(erro, ErroPipeline) else ""
            raise ErroPipeline(publico.codigo, detalhe) from erro

        self._emitir(user_id, "etapa_concluida", analise_id, definicao, progresso=100)
        return ResultadoEtapa("concluida", hash_entrada, tuple(executados), tuple(reaproveitados))

    def _hashes_das_entradas(
        self, etapa: Etapa, analise_id: uuid.UUID, user_id: uuid.UUID, video_id: uuid.UUID
    ) -> dict[str, str]:
        entradas: dict[str, str] = {}
        for nome in etapa.entradas:
            with self._fabrica() as sessao:
                artefatos = sessao.scalar(
                    select(ExecucaoEtapa.artefatos)
                    .where(
                        ExecucaoEtapa.analise_id == analise_id,
                        ExecucaoEtapa.user_id == user_id,
                        ExecucaoEtapa.etapa == nome,
                        ExecucaoEtapa.status == "concluida",
                    )
                    .order_by(ExecucaoEtapa.concluido_em.desc())
                    .limit(1)
                )
                sessao.commit()
            arquivos = [a for passo in (artefatos or {}).values() for a in passo["arquivos"]]
            if artefatos is None or not self._arquivos_integros(
                user_id, video_id, analise_id, arquivos
            ):
                raise ErroPipeline("ENTRADA_AUSENTE", f"etapa anterior {nome!r}")
            entradas[nome] = _hash_artefatos(arquivos)
        return entradas

    def _arquivos_integros(
        self,
        user_id: uuid.UUID,
        video_id: uuid.UUID,
        analise_id: uuid.UUID,
        arquivos: list[dict[str, Any]],
    ) -> bool:
        return all(
            self._armazenamento.verificar(
                user_id, video_id, _nome_fisico(analise_id, a["nome"]), a["sha256"]
            )
            for a in arquivos
        )

    def _reivindicar(
        self,
        etapa: Etapa,
        analise_id: uuid.UUID,
        user_id: uuid.UUID,
        video_id: uuid.UUID,
        hash_entrada: str,
    ) -> _Execucao | None:
        for _ in range(2):
            execucao, concluida = self._tentar_reivindicar(etapa, analise_id, user_id, hash_entrada)
            if execucao is not None:
                return execucao
            if concluida is None:
                return None
            if self._concluida_integra(etapa, concluida.artefatos, user_id, video_id, analise_id):
                return None
            # Artefato perdido ou alterado: a execução volta a ser refeita.
            with self._fabrica() as sessao:
                sessao.execute(
                    update(ExecucaoEtapa)
                    .where(ExecucaoEtapa.id == concluida.id, ExecucaoEtapa.status == "concluida")
                    .values(status="falhou")
                )
                sessao.commit()
        return None

    def _tentar_reivindicar(
        self, etapa: Etapa, analise_id: uuid.UUID, user_id: uuid.UUID, hash_entrada: str
    ) -> tuple[_Execucao | None, Any]:
        """Reivindica a linha ou devolve a execução concluída que precisa ser conferida."""
        chave = (
            ExecucaoEtapa.analise_id == analise_id,
            ExecucaoEtapa.user_id == user_id,
            ExecucaoEtapa.etapa == etapa.nome,
            ExecucaoEtapa.hash_entrada == hash_entrada,
        )
        vencimento = func.now() - timedelta(seconds=etapa.limite_s + self._lease_extra_s)
        with self._fabrica() as sessao:
            sessao.execute(
                inserir(ExecucaoEtapa)
                .values(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    analise_id=analise_id,
                    etapa=etapa.nome,
                    hash_entrada=hash_entrada,
                    status="pendente",
                    artefatos={},
                    metricas={},
                )
                .on_conflict_do_nothing(index_elements=["analise_id", "etapa", "hash_entrada"])
            )
            linha = sessao.execute(
                update(ExecucaoEtapa)
                .where(
                    *chave,
                    or_(
                        ExecucaoEtapa.status.in_(("pendente", "falhou")),
                        and_(
                            ExecucaoEtapa.status == "executando",
                            ExecucaoEtapa.iniciado_em < vencimento,
                        ),
                    ),
                )
                .values(status="executando", iniciado_em=func.now(), concluido_em=None)
                .returning(
                    ExecucaoEtapa.id,
                    ExecucaoEtapa.iniciado_em,
                    ExecucaoEtapa.artefatos,
                    ExecucaoEtapa.metricas,
                )
            ).first()
            atual = None
            if linha is None:
                atual = sessao.execute(
                    select(ExecucaoEtapa.id, ExecucaoEtapa.status, ExecucaoEtapa.artefatos).where(
                        *chave
                    )
                ).first()
            sessao.commit()
        if linha is not None:
            metricas = dict(linha.metricas or {})
            metricas.pop("erro_codigo", None)
            execucao = _Execucao(
                id=linha.id,
                iniciado_em=linha.iniciado_em,
                artefatos=dict(linha.artefatos or {}),
                metricas=metricas,
            )
            return execucao, None
        return None, (atual if atual is not None and atual.status == "concluida" else None)

    def _concluida_integra(
        self,
        etapa: Etapa,
        artefatos: dict[str, Any] | None,
        user_id: uuid.UUID,
        video_id: uuid.UUID,
        analise_id: uuid.UUID,
    ) -> bool:
        invalido = self._primeiro_passo_invalido(
            etapa, artefatos or {}, user_id, video_id, analise_id
        )
        return invalido == len(etapa.passos)

    def _resultado_sem_execucao(
        self, etapa: Etapa, analise_id: uuid.UUID, user_id: uuid.UUID, hash_entrada: str
    ) -> ResultadoEtapa:
        lease = timedelta(seconds=etapa.limite_s + self._lease_extra_s)
        with self._fabrica() as sessao:
            linha = sessao.execute(
                select(
                    ExecucaoEtapa.status,
                    func.extract("epoch", ExecucaoEtapa.iniciado_em + lease - func.now()).label(
                        "restante"
                    ),
                ).where(
                    ExecucaoEtapa.analise_id == analise_id,
                    ExecucaoEtapa.user_id == user_id,
                    ExecucaoEtapa.etapa == etapa.nome,
                    ExecucaoEtapa.hash_entrada == hash_entrada,
                )
            ).first()
            sessao.commit()
        if linha is not None and linha.status == "concluida":
            self._emitir(user_id, "etapa_pulada", analise_id, etapa, progresso=100)
            return ResultadoEtapa("pulada", hash_entrada, (), tuple(p.nome for p in etapa.passos))
        restante = max(0.0, float(linha.restante)) if linha is not None and linha.restante else 0.0
        return ResultadoEtapa("em_execucao", hash_entrada, (), (), lease_restante_s=restante)

    def _rodar_passos(
        self,
        etapa: Etapa,
        execucao: _Execucao,
        analise_id: uuid.UUID,
        user_id: uuid.UUID,
        video_id: uuid.UUID,
        parametros: Mapping[str, Any],
        executados: list[str],
        reaproveitados: list[str],
    ) -> None:
        with contextlib.ExitStack() as pilha:
            trava = None
            if etapa.usa_gpu:
                trava = pilha.enter_context(
                    TravaGpu(self._redis, ttl_ms=self._trava_ttl_ms, espera_s=self._trava_espera_s)
                )
            passos_metricas: dict[str, Any] = execucao.metricas.setdefault("passos", {})
            primeiro = self._primeiro_passo_invalido(
                etapa, execucao.artefatos, user_id, video_id, analise_id
            )
            for posterior in etapa.passos[primeiro:]:
                execucao.artefatos.pop(posterior.nome, None)
            if primeiro < len(etapa.passos):
                self._persistir(execucao)
            reaproveitados.extend(p.nome for p in etapa.passos[:primeiro])

            for indice, passo in enumerate(etapa.passos):
                if indice < primeiro:
                    continue
                anterior = passos_metricas.get(passo.nome, {})
                passos_metricas[passo.nome] = {
                    "execucoes": anterior.get("execucoes", 0) + 1,
                    "duracao_s": 0.0,
                }
                contexto = ContextoPasso(
                    user_id=user_id,
                    video_id=video_id,
                    analise_id=analise_id,
                    parametros=parametros,
                    armazenamento=self._armazenamento,
                    saidas=passo.saidas,
                    trava=trava,
                )
                # Uma saída que sobrou de outra execução não pode valer como saída deste passo.
                for nome in passo.saidas:
                    self._armazenamento.remover(user_id, video_id, _nome_fisico(analise_id, nome))
                inicio = time.monotonic()
                passo.executar(contexto)
                if trava is not None:
                    trava.garantir()
                execucao.artefatos[passo.nome] = {"arquivos": self._coletar_saidas(passo, contexto)}
                passos_metricas[passo.nome]["duracao_s"] = round(time.monotonic() - inicio, 3)
                self._persistir(execucao)
                executados.append(passo.nome)
                self._emitir(
                    user_id,
                    "passo_concluido",
                    analise_id,
                    etapa,
                    passo=passo.nome,
                    progresso=round(100 * (indice + 1) / len(etapa.passos), 1),
                )

    def _primeiro_passo_invalido(
        self,
        etapa: Etapa,
        artefatos: dict[str, Any],
        user_id: uuid.UUID,
        video_id: uuid.UUID,
        analise_id: uuid.UUID,
    ) -> int:
        for indice, passo in enumerate(etapa.passos):
            registro = artefatos.get(passo.nome)
            arquivos = registro["arquivos"] if registro else []
            declaradas = sorted(passo.saidas)
            if (
                not registro
                or sorted(a["nome"] for a in arquivos) != declaradas
                or not self._arquivos_integros(user_id, video_id, analise_id, arquivos)
            ):
                return indice
        return len(etapa.passos)

    def _coletar_saidas(self, passo: Passo, contexto: ContextoPasso) -> list[dict[str, Any]]:
        arquivos = []
        for nome in passo.saidas:
            fisico = _nome_fisico(contexto.analise_id, nome)
            if not self._armazenamento.existe(contexto.user_id, contexto.video_id, fisico):
                raise ErroPipeline("INTERNO", f"saída ausente: {nome!r}")
            sha256, tamanho = sha256_arquivo(contexto.caminho(nome))
            arquivos.append({"nome": nome, "sha256": sha256, "bytes": tamanho})
        return arquivos

    def _gravar(self, execucao: _Execucao, **valores: Any) -> bool:
        """Grava só enquanto esta execução ainda detém a linha reivindicada."""
        with self._fabrica() as sessao:
            resultado = sessao.execute(
                update(ExecucaoEtapa)
                .where(
                    ExecucaoEtapa.id == execucao.id,
                    ExecucaoEtapa.iniciado_em == execucao.iniciado_em,
                )
                .values(**valores)
            )
            sessao.commit()
        return resultado.rowcount == 1

    def _persistir(self, execucao: _Execucao) -> None:
        if not self._gravar(execucao, artefatos=execucao.artefatos, metricas=execucao.metricas):
            raise ErroPipeline("INTERNO", "execução reivindicada por outro worker")

    def _concluir(self, execucao: _Execucao) -> None:
        if not self._gravar(
            execucao, status="concluida", concluido_em=func.now(), metricas=execucao.metricas
        ):
            raise ErroPipeline("INTERNO", "execução reivindicada por outro worker")

    def _logar_falha(
        self, etapa: Etapa, analise_id: uuid.UUID, codigo: str, erro: BaseException
    ) -> None:
        detalhe = erro.detalhe if isinstance(erro, ErroPipeline) else str(erro)
        # Detalhe e rastreio vão escapados em uma única linha, sem quebras vindas da entrada.
        rastreio = "".join(traceback.format_exception(erro))[-3000:]
        logger.error(
            f"Etapa {etapa.nome} falhou ({codigo}) na análise {analise_id}: "
            f"{type(erro).__name__}: {detalhe[:500]!r} rastreio={rastreio!r}"
        )

    def _registrar_falha_previa(
        self,
        etapa: Etapa,
        analise_id: uuid.UUID,
        user_id: uuid.UUID,
        causa: Exception,
        erro: ErroPipeline,
    ) -> None:
        self._logar_falha(etapa, analise_id, erro.codigo, causa)
        try:
            self._marcar_analise(
                analise_id, user_id, status="falhou", etapa=etapa.nome, erro=erro.mensagem
            )
        except Exception as falha:
            logger.error(f"Falha ao registrar o erro da etapa: {type(falha).__name__}")
        self._emitir(
            user_id,
            "erro",
            analise_id,
            etapa,
            codigo=erro.codigo,
            mensagem=erro.mensagem,
        )

    def _registrar_falha(
        self,
        etapa: Etapa,
        execucao: _Execucao,
        analise_id: uuid.UUID,
        user_id: uuid.UUID,
        erro: BaseException,
    ) -> None:
        publico = traduzir(erro)
        self._logar_falha(etapa, analise_id, publico.codigo, erro)
        execucao.metricas["erro_codigo"] = publico.codigo
        try:
            detida = self._gravar(
                execucao, status="falhou", artefatos=execucao.artefatos, metricas=execucao.metricas
            )
            if not detida:
                logger.warning(f"Etapa {etapa.nome}: execução já pertence a outro worker.")
                return
            self._marcar_analise(
                analise_id, user_id, status="falhou", etapa=etapa.nome, erro=publico.mensagem
            )
        except Exception as falha:
            logger.error(f"Falha ao registrar o erro da etapa: {type(falha).__name__}")
        self._emitir(
            user_id,
            "erro",
            analise_id,
            etapa,
            codigo=publico.codigo,
            mensagem=publico.mensagem,
        )

    def _marcar_analise(
        self,
        analise_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        status: str,
        etapa: str,
        erro: str | None = None,
    ) -> None:
        with self._fabrica() as sessao:
            sessao.execute(
                update(Analise)
                .where(Analise.id == analise_id, Analise.user_id == user_id)
                .values(status=status, etapa_atual=etapa, erro_amigavel=erro)
            )
            sessao.commit()

    def _emitir(
        self,
        user_id: uuid.UUID,
        tipo: TipoEvento,
        analise_id: uuid.UUID,
        etapa: Etapa,
        *,
        passo: str | None = None,
        progresso: float = 0,
        codigo: str | None = None,
        mensagem: str | None = None,
    ) -> None:
        self._eventos.publicar(
            user_id,
            EventoAnalise(
                tipo=tipo,
                analise_id=analise_id,
                etapa=etapa.nome,
                passo=passo,
                progresso_etapa=progresso,
                codigo=codigo,
                mensagem=mensagem,
            ),
        )
