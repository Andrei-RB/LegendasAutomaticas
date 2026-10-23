import uuid
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from pydantic import SecretStr
from sqlalchemy import ForeignKeyConstraint, UniqueConstraint, delete, func, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.nucleo.config import settings

TABELAS = {
    "usuarios",
    "videos",
    "analises",
    "execucoes_etapa",
    "candidatos",
    "julgamentos",
    "cortes",
    "documentos_legenda",
    "modelos_legenda",
    "fontes",
    "exportacoes",
    "textos_postagem",
    "cache_hashtags",
    "hashtags_usuario",
    "chamadas_ia",
    "feedback",
}
SEM_USER_ID = {"usuarios", "cache_hashtags"}
USER_ID_NULAVEL = {"modelos_legenda", "fontes"}
SEGREDO = "segredo-xyz-123"
URL_COM_SEGREDO = f"postgresql+psycopg://usuario:{SEGREDO}@localhost:5432/viraliza"

PAIS_COM_DONO = {"videos", "analises", "candidatos", "cortes", "documentos_legenda"}
# (tabela, coluna) -> pai referenciado por FK composta (coluna, user_id).
COMPOSTAS = {
    ("analises", "video_id"): "videos",
    ("execucoes_etapa", "analise_id"): "analises",
    ("candidatos", "analise_id"): "analises",
    ("julgamentos", "candidato_id"): "candidatos",
    ("cortes", "analise_id"): "analises",
    ("cortes", "candidato_id"): "candidatos",
    ("documentos_legenda", "corte_id"): "cortes",
    ("exportacoes", "corte_id"): "cortes",
    ("exportacoes", "documento_legenda_id"): "documentos_legenda",
    ("textos_postagem", "corte_id"): "cortes",
    ("chamadas_ia", "analise_id"): "analises",
    ("feedback", "corte_id"): "cortes",
    ("feedback", "candidato_id"): "candidatos",
}
COMPOSTAS_NULAVEIS = {
    ("cortes", "candidato_id"),
    ("exportacoes", "documento_legenda_id"),
    ("chamadas_ia", "analise_id"),
    ("feedback", "corte_id"),
    ("feedback", "candidato_id"),
}


@pytest.fixture
def metadados():
    from app.modelos import Base

    return Base.metadata


@pytest.fixture
def fabrica(banco_migrado: str):
    from app.nucleo.banco import criar_fabrica_sessao, criar_motor

    motor = criar_motor(banco_migrado)
    yield criar_fabrica_sessao(motor)
    motor.dispose()


@pytest.fixture
def sessao(fabrica):
    with fabrica() as s:
        yield s


@contextmanager
def _viola(sessao: Session, restricao: str):
    """Exige IntegrityError cuja restrição violada seja `restricao`; a sessão segue utilizável."""
    with pytest.raises(IntegrityError) as erro:
        with sessao.begin_nested():
            yield
    assert erro.value.orig.diag.constraint_name == restricao


def _criar_usuario(sessao: Session, nome: str = "usuario_a"):
    from app.modelos import Usuario

    usuario = Usuario(nome_usuario=f"{nome}_{uuid.uuid4().hex[:8]}")
    sessao.add(usuario)
    sessao.flush()
    return usuario


def _criar_video(sessao: Session, user_id: uuid.UUID):
    from app.modelos import Video

    video = Video(user_id=user_id, origem="arquivo", caminho_original="/dados/video.mp4")
    sessao.add(video)
    sessao.flush()
    return video


def _criar_analise(
    sessao: Session, user_id: uuid.UUID, video_id: uuid.UUID, parametros=None, progresso=0
):
    from app.modelos import Analise

    analise = Analise(
        user_id=user_id,
        video_id=video_id,
        parametros=parametros if parametros is not None else {},
        etapa_atual="ingestao",
        progresso=progresso,
    )
    sessao.add(analise)
    sessao.flush()
    return analise


def _criar_execucao(sessao: Session, analise, etapa: str, hash_entrada: str):
    from app.modelos import ExecucaoEtapa

    execucao = ExecucaoEtapa(
        user_id=analise.user_id,
        analise_id=analise.id,
        etapa=etapa,
        hash_entrada=hash_entrada,
        status="pendente",
    )
    sessao.add(execucao)
    sessao.flush()
    return execucao


def _criar_candidato(sessao: Session, analise, inicio_s: float = 10.0, fim_s: float = 40.0):
    from app.modelos import Candidato

    candidato = Candidato(
        user_id=analise.user_id,
        analise_id=analise.id,
        inicio_s=inicio_s,
        fim_s=fim_s,
        id_frase_inicial=1,
        id_frase_final=5,
    )
    sessao.add(candidato)
    sessao.flush()
    return candidato


def _criar_corte(
    sessao: Session, analise, candidato=None, inicio_s: float = 10.0, fim_s: float = 40.0
):
    from app.modelos import Corte

    corte = Corte(
        user_id=analise.user_id,
        analise_id=analise.id,
        candidato_id=candidato.id if candidato else None,
        inicio_s=inicio_s,
        fim_s=fim_s,
    )
    sessao.add(corte)
    sessao.flush()
    return corte


def _criar_documento(sessao: Session, corte, versao: int = 1):
    from app.modelos import DocumentoLegenda

    documento = DocumentoLegenda(
        user_id=corte.user_id, corte_id=corte.id, versao=versao, conteudo={"blocos": []}
    )
    sessao.add(documento)
    sessao.flush()
    return documento


def _criar_modelo_legenda(sessao: Session, user_id: uuid.UUID | None):
    from app.modelos import ModeloLegenda

    modelo = ModeloLegenda(user_id=user_id, nome="padrao", especificacao={"fonte": "x"})
    sessao.add(modelo)
    sessao.flush()
    return modelo


def _criar_exportacao(sessao: Session, user_id, corte_id, modelo_id=None, documento_id=None):
    from app.modelos import Exportacao

    exportacao = Exportacao(
        user_id=user_id,
        corte_id=corte_id,
        modelo_legenda_id=modelo_id,
        documento_legenda_id=documento_id,
    )
    sessao.add(exportacao)
    sessao.flush()
    return exportacao


def _criar_feedback(sessao: Session, user_id, corte_id=None, candidato_id=None):
    from app.modelos import Feedback

    feedback = Feedback(
        user_id=user_id, corte_id=corte_id, candidato_id=candidato_id, aprovado=True
    )
    sessao.add(feedback)
    sessao.flush()
    return feedback


def _montar_grafo(sessao: Session, nome: str) -> SimpleNamespace:
    """Cria um usuário com ao menos uma linha em cada tabela que possui user_id."""
    from app.modelos import (
        ChamadaIa,
        Fonte,
        HashtagUsuario,
        Julgamento,
        TextoPostagem,
    )

    g = SimpleNamespace()
    g.usuario = _criar_usuario(sessao, nome)
    uid = g.usuario.id
    g.video = _criar_video(sessao, uid)
    g.analise = _criar_analise(sessao, uid, g.video.id)
    g.execucao = _criar_execucao(sessao, g.analise, "sinais", "hash-a")
    g.candidato = _criar_candidato(sessao, g.analise)
    g.julgamento = Julgamento(
        user_id=uid,
        candidato_id=g.candidato.id,
        juiz="qwen",
        modelo="qwen-9b",
        versao_prompt="v1",
        valido=True,
    )
    sessao.add(g.julgamento)
    g.corte = _criar_corte(sessao, g.analise, g.candidato)
    g.documento = _criar_documento(sessao, g.corte)
    g.modelo = _criar_modelo_legenda(sessao, uid)
    g.exportacao = _criar_exportacao(sessao, uid, g.corte.id, g.modelo.id, g.documento.id)
    g.texto = TextoPostagem(user_id=uid, corte_id=g.corte.id, plataforma="tiktok")
    g.chamada = ChamadaIa(
        user_id=uid,
        analise_id=g.analise.id,
        tarefa="triagem",
        provedor="qwen",
        modelo="qwen-9b",
        status="ok",
    )
    g.fonte = Fonte(user_id=uid, familia="Inter", origem="sistema", caminho="/recursos/inter.ttf")
    g.hashtag = HashtagUsuario(user_id=uid, hashtag="#viral")
    g.feedback = _criar_feedback(sessao, uid, g.corte.id, g.candidato.id)
    sessao.add_all([g.texto, g.chamada, g.fonte, g.hashtag])
    sessao.flush()
    return g


def _contar(sessao: Session, modelo, user_id: uuid.UUID) -> int:
    consulta = select(func.count()).select_from(modelo).where(modelo.user_id == user_id)
    return sessao.execute(consulta).scalar_one()


def test_database_url_padrao_vazio():
    padrao = type(settings).model_fields["DATABASE_URL"].default
    assert (padrao.get_secret_value() if isinstance(padrao, SecretStr) else padrao) == ""


def test_database_url_e_segredo_e_nao_aparece_em_repr_nem_dump():
    from app.nucleo.config import Settings

    config = Settings(DATABASE_URL=URL_COM_SEGREDO, _env_file=None)
    assert isinstance(config.DATABASE_URL, SecretStr)
    assert config.DATABASE_URL.get_secret_value() == URL_COM_SEGREDO
    assert SEGREDO not in repr(config)
    assert SEGREDO not in str(config)
    assert SEGREDO not in repr(config.model_dump())


def test_metadados_contem_exatamente_as_16_tabelas(metadados):
    assert set(metadados.tables) == TABELAS


def test_modelos_expoem_base_do_modulo_banco(metadados):
    from app.nucleo.banco import Base

    assert Base.metadata is metadados


def test_tabelas_de_dominio_tem_user_id_com_fk_e_indice(metadados):
    for nome in TABELAS - SEM_USER_ID:
        tabela = metadados.tables[nome]
        assert "user_id" in tabela.c, f"{nome}: sem coluna user_id"
        para_usuarios = [
            fk for fk in tabela.c.user_id.foreign_keys if fk.target_fullname == "usuarios.id"
        ]
        assert len(para_usuarios) == 1, f"{nome}: FK de user_id para usuarios.id ausente"
        assert any(ix.columns.keys()[0] == "user_id" for ix in tabela.indexes), (
            f"{nome}: sem índice iniciado por user_id"
        )


def test_fk_de_user_id_remove_em_cascata(metadados):
    for nome in TABELAS - SEM_USER_ID:
        fks = [
            fk
            for fk in metadados.tables[nome].c.user_id.foreign_keys
            if fk.target_fullname == "usuarios.id"
        ]
        assert fks, f"{nome}: sem FK de user_id para usuarios.id"
        for fk in fks:
            assert fk.ondelete == "CASCADE", f"{nome}: user_id sem ON DELETE CASCADE"


def test_user_id_nulo_apenas_em_registros_de_sistema(metadados):
    for nome in TABELAS - SEM_USER_ID:
        nulavel = metadados.tables[nome].c.user_id.nullable
        assert nulavel == (nome in USER_ID_NULAVEL), f"{nome}: nulabilidade de user_id incorreta"


def test_cache_hashtags_global_sem_user_id(metadados):
    assert "user_id" not in metadados.tables["cache_hashtags"].c
    assert "user_id" not in metadados.tables["usuarios"].c


def test_pais_tem_unicidade_id_user_id(metadados):
    for nome in PAIS_COM_DONO:
        tabela = metadados.tables[nome]
        unicos = [
            set(c.columns.keys()) for c in tabela.constraints if isinstance(c, UniqueConstraint)
        ]
        unicos += [set(ix.columns.keys()) for ix in tabela.indexes if ix.unique]
        assert {"id", "user_id"} in unicos, f"{nome}: sem UNIQUE (id, user_id)"


def _fks_compostas(metadados):
    achadas = {}
    for tabela in metadados.tables.values():
        for c in tabela.constraints:
            if isinstance(c, ForeignKeyConstraint) and len(c.elements) > 1:
                achadas[(tabela.name, c.elements[0].parent.name)] = c
    return achadas


def test_fks_compostas_terminam_em_user_id_e_apontam_para_user_id_do_pai(metadados):
    achadas = _fks_compostas(metadados)
    assert {chave: c.referred_table.name for chave, c in achadas.items()} == COMPOSTAS
    for (tabela, coluna), c in achadas.items():
        pai = COMPOSTAS[(tabela, coluna)]
        assert [e.parent.name for e in c.elements] == [coluna, "user_id"]
        assert [e.target_fullname for e in c.elements] == [f"{pai}.id", f"{pai}.user_id"]


def test_fks_compostas_removem_em_cascata_ou_anulam_apenas_a_coluna(metadados):
    for (tabela, coluna), c in _fks_compostas(metadados).items():
        nulavel = (tabela, coluna) in COMPOSTAS_NULAVEIS
        assert c.ondelete == (f"SET NULL ({coluna})" if nulavel else "CASCADE"), (tabela, coluna)
        assert metadados.tables[tabela].c[coluna].nullable == nulavel, (tabela, coluna)


def test_modelo_legenda_id_e_fk_simples(metadados):
    tabela = metadados.tables["exportacoes"]
    fks = [
        c
        for c in tabela.constraints
        if isinstance(c, ForeignKeyConstraint) and "modelo_legenda_id" in c.columns
    ]
    assert len(fks) == 1
    assert len(fks[0].elements) == 1
    assert fks[0].elements[0].target_fullname == "modelos_legenda.id"


def test_chaves_primarias_sao_uuid(metadados):
    from sqlalchemy import Uuid

    for nome in TABELAS - {"cache_hashtags"}:
        pk = list(metadados.tables[nome].primary_key.columns)
        assert len(pk) == 1, f"{nome}: chave primária composta"
        assert isinstance(pk[0].type, Uuid), f"{nome}: chave primária não é UUID"


def test_execucoes_etapa_tem_unicidade_analise_etapa_hash(metadados):
    from sqlalchemy import UniqueConstraint

    tabela = metadados.tables["execucoes_etapa"]
    alvo = {"analise_id", "etapa", "hash_entrada"}
    unicos = [set(c.columns.keys()) for c in tabela.constraints if isinstance(c, UniqueConstraint)]
    unicos += [set(ix.columns.keys()) for ix in tabela.indexes if ix.unique]
    assert alvo in unicos


def test_criar_motor_rejeita_url_vazia():
    from app.nucleo.banco import criar_motor

    for url in ("", "   "):
        with pytest.raises(ValueError, match="DATABASE_URL"):
            criar_motor(url)


def test_criar_motor_usa_psycopg_com_pre_ping_sem_expor_senha():
    from app.nucleo.banco import criar_motor

    motor = criar_motor(URL_COM_SEGREDO)
    try:
        assert motor.dialect.driver == "psycopg"
        assert motor.pool._pre_ping is True
        assert motor.hide_parameters is True
        assert SEGREDO not in repr(motor)
    finally:
        motor.dispose()


def test_criar_motor_nao_vaza_senha_em_url_invalida():
    from app.nucleo.banco import criar_motor

    with pytest.raises((ValueError, SQLAlchemyError)) as erro:
        criar_motor(f"sem-esquema:{SEGREDO}")
    assert SEGREDO not in str(erro.value)
    assert SEGREDO not in repr(erro.value)


def test_criar_fabrica_sessao_vincula_ao_motor(url_banco_teste):
    from app.nucleo.banco import criar_fabrica_sessao, criar_motor

    motor = criar_motor(url_banco_teste)
    try:
        fabrica = criar_fabrica_sessao(motor)
        assert isinstance(fabrica, sessionmaker)
        with fabrica() as s:
            assert s.get_bind() is motor
            assert s.execute(select(1)).scalar_one() == 1
    finally:
        motor.dispose()


def test_execucao_duplicada_viola_unicidade(sessao):
    usuario = _criar_usuario(sessao)
    analise = _criar_analise(sessao, usuario.id, _criar_video(sessao, usuario.id).id)
    _criar_execucao(sessao, analise, "sinais", "hash-a")
    with _viola(sessao, "uq_execucoes_etapa_analise_id_etapa_hash_entrada"):
        _criar_execucao(sessao, analise, "sinais", "hash-a")


def test_mesma_etapa_com_hash_diferente_e_aceita(sessao):
    from app.modelos import ExecucaoEtapa

    usuario = _criar_usuario(sessao)
    analise = _criar_analise(sessao, usuario.id, _criar_video(sessao, usuario.id).id)
    _criar_execucao(sessao, analise, "sinais", "hash-a")
    _criar_execucao(sessao, analise, "sinais", "hash-b")
    _criar_execucao(sessao, analise, "ingestao", "hash-a")
    assert _contar(sessao, ExecucaoEtapa, usuario.id) == 3


def test_video_com_user_id_inexistente_viola_fk(sessao):
    with _viola(sessao, "fk_videos_user_id_usuarios"):
        _criar_video(sessao, uuid.uuid4())


def test_documento_duplicado_para_mesmo_corte_e_versao_viola_unicidade(sessao):
    g = _montar_grafo(sessao, "a")
    _criar_documento(sessao, g.corte, versao=2)
    with _viola(sessao, "uq_documentos_legenda_corte_id_versao"):
        _criar_documento(sessao, g.corte, versao=2)


def test_hashtag_duplicada_do_mesmo_usuario_viola_unicidade_mas_outro_usuario_aceita(sessao):
    from app.modelos import HashtagUsuario

    a = _criar_usuario(sessao, "a")
    b = _criar_usuario(sessao, "b")
    sessao.add(HashtagUsuario(user_id=a.id, hashtag="#viral"))
    sessao.add(HashtagUsuario(user_id=b.id, hashtag="#viral"))
    sessao.flush()
    with _viola(sessao, "uq_hashtags_usuario_user_id_hashtag"):
        sessao.add(HashtagUsuario(user_id=a.id, hashtag="#viral"))
        sessao.flush()


def test_cache_hashtags_duplicado_por_nicho_e_plataforma_viola_unicidade(sessao):
    from app.modelos import CacheHashtags

    sessao.add(CacheHashtags(nicho="games", plataforma="tiktok"))
    sessao.add(CacheHashtags(nicho="games", plataforma="reels"))
    sessao.flush()
    with _viola(sessao, "uq_cache_hashtags_nicho_plataforma"):
        sessao.add(CacheHashtags(nicho="games", plataforma="tiktok"))
        sessao.flush()


@pytest.mark.parametrize("progresso", [-1, 101])
def test_progresso_fora_da_faixa_viola(sessao, progresso):
    usuario = _criar_usuario(sessao)
    video = _criar_video(sessao, usuario.id)
    with _viola(sessao, "ck_analises_progresso_faixa"):
        _criar_analise(sessao, usuario.id, video.id, progresso=progresso)


@pytest.mark.parametrize("progresso", [0, 100])
def test_progresso_nos_limites_e_aceito(sessao, progresso):
    usuario = _criar_usuario(sessao)
    video = _criar_video(sessao, usuario.id)
    _criar_analise(sessao, usuario.id, video.id, progresso=progresso)


@pytest.mark.parametrize(("inicio_s", "fim_s"), [(10.0, 10.0), (10.0, 5.0)])
def test_candidato_com_fim_nao_posterior_ao_inicio_viola(sessao, inicio_s, fim_s):
    usuario = _criar_usuario(sessao)
    analise = _criar_analise(sessao, usuario.id, _criar_video(sessao, usuario.id).id)
    with _viola(sessao, "ck_candidatos_intervalo_valido"):
        _criar_candidato(sessao, analise, inicio_s, fim_s)


@pytest.mark.parametrize(("inicio_s", "fim_s"), [(10.0, 10.0), (10.0, 5.0)])
def test_corte_com_fim_nao_posterior_ao_inicio_viola(sessao, inicio_s, fim_s):
    usuario = _criar_usuario(sessao)
    analise = _criar_analise(sessao, usuario.id, _criar_video(sessao, usuario.id).id)
    with _viola(sessao, "ck_cortes_intervalo_valido"):
        _criar_corte(sessao, analise, None, inicio_s, fim_s)


def _isolar_analise(s, a, b):
    _criar_analise(s, a.usuario.id, b.video.id)


def _isolar_execucao(s, a, b):
    from app.modelos import ExecucaoEtapa

    s.add(
        ExecucaoEtapa(
            user_id=a.usuario.id,
            analise_id=b.analise.id,
            etapa="sinais",
            hash_entrada="x",
            status="pendente",
        )
    )
    s.flush()


def _isolar_candidato(s, a, b):
    from app.modelos import Candidato

    s.add(
        Candidato(
            user_id=a.usuario.id,
            analise_id=b.analise.id,
            inicio_s=1,
            fim_s=2,
            id_frase_inicial=1,
            id_frase_final=2,
        )
    )
    s.flush()


def _isolar_julgamento(s, a, b):
    from app.modelos import Julgamento

    s.add(
        Julgamento(
            user_id=a.usuario.id,
            candidato_id=b.candidato.id,
            juiz="qwen",
            modelo="m",
            versao_prompt="v1",
            valido=True,
        )
    )
    s.flush()


def _isolar_corte_analise(s, a, b):
    from app.modelos import Corte

    s.add(Corte(user_id=a.usuario.id, analise_id=b.analise.id, inicio_s=1, fim_s=2))
    s.flush()


def _isolar_corte_candidato(s, a, b):
    from app.modelos import Corte

    s.add(
        Corte(
            user_id=a.usuario.id,
            analise_id=a.analise.id,
            candidato_id=b.candidato.id,
            inicio_s=1,
            fim_s=2,
        )
    )
    s.flush()


def _isolar_documento(s, a, b):
    from app.modelos import DocumentoLegenda

    s.add(DocumentoLegenda(user_id=a.usuario.id, corte_id=b.corte.id, versao=9, conteudo={}))
    s.flush()


def _isolar_exportacao_corte(s, a, b):
    _criar_exportacao(s, a.usuario.id, b.corte.id)


def _isolar_exportacao_documento(s, a, b):
    _criar_exportacao(s, a.usuario.id, a.corte.id, documento_id=b.documento.id)


def _isolar_feedback_corte(s, a, b):
    _criar_feedback(s, a.usuario.id, corte_id=b.corte.id)


def _isolar_feedback_candidato(s, a, b):
    _criar_feedback(s, a.usuario.id, candidato_id=b.candidato.id)


def _isolar_texto(s, a, b):
    from app.modelos import TextoPostagem

    s.add(TextoPostagem(user_id=a.usuario.id, corte_id=b.corte.id, plataforma="reels"))
    s.flush()


def _isolar_chamada(s, a, b):
    from app.modelos import ChamadaIa

    s.add(
        ChamadaIa(
            user_id=a.usuario.id,
            analise_id=b.analise.id,
            tarefa="triagem",
            provedor="qwen",
            modelo="m",
            status="ok",
        )
    )
    s.flush()


ISOLAMENTO = [
    (_isolar_analise, "fk_analises_video_id_videos"),
    (_isolar_execucao, "fk_execucoes_etapa_analise_id_analises"),
    (_isolar_candidato, "fk_candidatos_analise_id_analises"),
    (_isolar_julgamento, "fk_julgamentos_candidato_id_candidatos"),
    (_isolar_corte_analise, "fk_cortes_analise_id_analises"),
    (_isolar_corte_candidato, "fk_cortes_candidato_id_candidatos"),
    (_isolar_documento, "fk_documentos_legenda_corte_id_cortes"),
    (_isolar_exportacao_corte, "fk_exportacoes_corte_id_cortes"),
    (_isolar_exportacao_documento, "fk_exportacoes_documento_legenda_id_documentos_legenda"),
    (_isolar_feedback_corte, "fk_feedback_corte_id_cortes"),
    (_isolar_feedback_candidato, "fk_feedback_candidato_id_candidatos"),
    (_isolar_texto, "fk_textos_postagem_corte_id_cortes"),
    (_isolar_chamada, "fk_chamadas_ia_analise_id_analises"),
]


@pytest.mark.parametrize(
    ("criar", "restricao"), ISOLAMENTO, ids=[c.__name__ for c, _ in ISOLAMENTO]
)
def test_filha_nao_referencia_pai_de_outro_usuario(sessao, criar, restricao):
    a = _montar_grafo(sessao, "a")
    b = _montar_grafo(sessao, "b")
    with _viola(sessao, restricao):
        criar(sessao, a, b)


def test_exportacao_com_modelo_de_outro_usuario_e_rejeitada_pelo_gatilho(sessao):
    a = _montar_grafo(sessao, "a")
    b = _montar_grafo(sessao, "b")
    with pytest.raises(IntegrityError) as erro:
        with sessao.begin_nested():
            _criar_exportacao(sessao, a.usuario.id, a.corte.id, modelo_id=b.modelo.id)
    assert erro.value.orig.sqlstate == "23503"
    assert erro.value.orig.diag.constraint_name == "ck_exportacoes_modelo_dono"


def test_troca_de_modelo_na_exportacao_por_modelo_de_outro_usuario_e_rejeitada(sessao):
    a = _montar_grafo(sessao, "a")
    b = _montar_grafo(sessao, "b")
    exportacao = _criar_exportacao(sessao, a.usuario.id, a.corte.id, modelo_id=a.modelo.id)
    with _viola(sessao, "ck_exportacoes_modelo_dono"):
        exportacao.modelo_legenda_id = b.modelo.id
        sessao.flush()


def test_exportacao_aceita_modelo_de_sistema_e_modelo_do_proprio_usuario(sessao):
    from app.modelos import Exportacao

    a = _montar_grafo(sessao, "a")
    sistema = _criar_modelo_legenda(sessao, None)
    _criar_exportacao(sessao, a.usuario.id, a.corte.id, modelo_id=sistema.id)
    _criar_exportacao(sessao, a.usuario.id, a.corte.id, modelo_id=a.modelo.id)
    assert _contar(sessao, Exportacao, a.usuario.id) == 3


def test_dono_do_modelo_de_legenda_e_imutavel(sessao):
    a = _montar_grafo(sessao, "a")
    b = _criar_usuario(sessao, "b")
    sistema = _criar_modelo_legenda(sessao, None)
    for modelo, novo_dono in ((a.modelo, b.id), (a.modelo, None), (sistema, a.usuario.id)):
        with _viola(sessao, "ck_modelos_legenda_user_id_imutavel"):
            modelo.user_id = novo_dono
            sessao.flush()
        sessao.refresh(modelo)


def test_exclusao_de_usuario_remove_grafo_completo_em_cascata(sessao, metadados):
    from app.modelos import Usuario

    alvo = _montar_grafo(sessao, "alvo")
    outro = _montar_grafo(sessao, "outro")
    tabelas = [metadados.tables[n] for n in sorted(TABELAS - SEM_USER_ID)]

    def contar(tabela, user_id):
        consulta = select(func.count()).select_from(tabela).where(tabela.c.user_id == user_id)
        return sessao.execute(consulta).scalar_one()

    antes = {t.name: contar(t, outro.usuario.id) for t in tabelas}
    assert all(n >= 1 for n in antes.values()), antes
    assert all(contar(t, alvo.usuario.id) >= 1 for t in tabelas)

    sessao.execute(delete(Usuario).where(Usuario.id == alvo.usuario.id))

    for t in tabelas:
        assert contar(t, alvo.usuario.id) == 0, t.name
        assert contar(t, outro.usuario.id) == antes[t.name], t.name


def test_apagar_corte_mantem_feedback_com_corte_nulo(sessao):
    from app.modelos import Corte, Feedback

    g = _montar_grafo(sessao, "a")
    sessao.execute(delete(Corte).where(Corte.id == g.corte.id))
    linha = sessao.execute(
        select(Feedback.corte_id, Feedback.candidato_id, Feedback.user_id).where(
            Feedback.id == g.feedback.id
        )
    ).one()
    assert linha.corte_id is None
    assert linha.candidato_id == g.candidato.id
    assert linha.user_id == g.usuario.id


def test_apagar_candidato_mantem_corte_e_feedback_com_candidato_nulo(sessao):
    from app.modelos import Candidato, Corte, Feedback

    g = _montar_grafo(sessao, "a")
    sessao.execute(delete(Candidato).where(Candidato.id == g.candidato.id))
    corte = sessao.execute(
        select(Corte.candidato_id, Corte.user_id, Corte.analise_id).where(Corte.id == g.corte.id)
    ).one()
    assert corte.candidato_id is None
    assert corte.user_id == g.usuario.id
    assert corte.analise_id == g.analise.id
    feedback = sessao.execute(
        select(Feedback.candidato_id, Feedback.corte_id, Feedback.user_id).where(
            Feedback.id == g.feedback.id
        )
    ).one()
    assert feedback.candidato_id is None
    assert feedback.corte_id == g.corte.id
    assert feedback.user_id == g.usuario.id


def test_apagar_analise_mantem_chamada_ia_com_analise_nula(sessao):
    from app.modelos import Analise, ChamadaIa

    g = _montar_grafo(sessao, "a")
    sessao.execute(delete(Analise).where(Analise.id == g.analise.id))
    linha = sessao.execute(
        select(ChamadaIa.analise_id, ChamadaIa.user_id).where(ChamadaIa.id == g.chamada.id)
    ).one()
    assert linha.analise_id is None
    assert linha.user_id == g.usuario.id


def test_feedback_aceita_corte_e_candidato_nulos_e_instantaneo_padrao_vazio(sessao):
    from app.modelos import Feedback

    usuario = _criar_usuario(sessao)
    feedback = _criar_feedback(sessao, usuario.id)
    sessao.commit()
    sessao.expire_all()
    lido = sessao.execute(
        select(Feedback.instantaneo, Feedback.corte_id, Feedback.candidato_id).where(
            Feedback.id == feedback.id
        )
    ).one()
    assert lido.instantaneo == {}
    assert lido.corte_id is None
    assert lido.candidato_id is None


def test_feedback_instantaneo_e_jsonb_e_preserva_dict_com_unicode(sessao, banco_migrado):
    from app.modelos import Feedback
    from app.nucleo.banco import criar_motor

    usuario = _criar_usuario(sessao)
    instantaneo = {"nota": 8.5, "motivo": "ótimo — 日本語", "itens": [1, {"a": None}]}
    feedback = Feedback(user_id=usuario.id, aprovado=False, instantaneo=instantaneo)
    sessao.add(feedback)
    sessao.commit()
    sessao.expire_all()
    lido = sessao.execute(select(Feedback.instantaneo).where(Feedback.id == feedback.id))
    assert lido.scalar_one() == instantaneo
    motor = criar_motor(banco_migrado)
    try:
        colunas = {c["name"]: c["type"] for c in sa_inspect(motor).get_columns("feedback")}
        assert isinstance(colunas["instantaneo"], postgresql.JSONB)
    finally:
        motor.dispose()


def test_jsonb_dict_mutado_no_lugar_e_persistido(sessao, fabrica):
    from app.modelos import ExecucaoEtapa

    usuario = _criar_usuario(sessao)
    analise = _criar_analise(sessao, usuario.id, _criar_video(sessao, usuario.id).id)
    execucao = _criar_execucao(sessao, analise, "sinais", "hash-a")
    sessao.commit()
    sessao.expire_all()

    carregada = sessao.get(ExecucaoEtapa, execucao.id)
    carregada.metricas["x"] = 1
    sessao.commit()

    with fabrica() as outra:
        assert outra.get(ExecucaoEtapa, execucao.id).metricas == {"x": 1}


def test_jsonb_lista_com_append_e_persistida(sessao, fabrica):
    from app.modelos import Candidato

    usuario = _criar_usuario(sessao)
    analise = _criar_analise(sessao, usuario.id, _criar_video(sessao, usuario.id).id)
    candidato = _criar_candidato(sessao, analise)
    sessao.commit()
    sessao.expire_all()

    carregado = sessao.get(Candidato, candidato.id)
    carregado.variantes.append({"inicio_s": 1.0})
    sessao.commit()

    with fabrica() as outra:
        assert outra.get(Candidato, candidato.id).variantes == [{"inicio_s": 1.0}]


def test_insert_sql_puro_usa_defaults_de_servidor(sessao):
    usuario = _criar_usuario(sessao)
    video = _criar_video(sessao, usuario.id)
    sessao.execute(
        text(
            "INSERT INTO analises (id, user_id, video_id, parametros) "
            "VALUES (gen_random_uuid(), :u, :v, '{}'::jsonb)"
        ),
        {"u": usuario.id, "v": video.id},
    )
    sessao.execute(
        text("INSERT INTO cache_hashtags (nicho, plataforma) VALUES ('games', 'tiktok')")
    )
    atualizado = sessao.execute(
        text("SELECT atualizado_em FROM analises WHERE user_id = :u"), {"u": usuario.id}
    ).scalar_one()
    buscado = sessao.execute(text("SELECT buscado_em FROM cache_hashtags")).scalar_one()
    assert atualizado is not None
    assert buscado is not None


def test_expira_em_e_timestamptz(banco_migrado):
    from app.nucleo.banco import criar_motor

    motor = criar_motor(banco_migrado)
    try:
        inspetor = sa_inspect(motor)
        for tabela in ("videos", "cortes"):
            colunas = {c["name"]: c["type"] for c in inspetor.get_columns(tabela)}
            tipo = colunas["expira_em"]
            assert isinstance(tipo, postgresql.TIMESTAMP)
            assert tipo.timezone is True
    finally:
        motor.dispose()


def test_colunas_de_documento_e_modelo_sao_jsonb(banco_migrado):
    from app.nucleo.banco import criar_motor

    motor = criar_motor(banco_migrado)
    try:
        inspetor = sa_inspect(motor)
        alvos = (("documentos_legenda", "conteudo"), ("modelos_legenda", "especificacao"))
        for tabela, coluna in alvos:
            colunas = {c["name"]: c["type"] for c in inspetor.get_columns(tabela)}
            assert isinstance(colunas[coluna], postgresql.JSONB), f"{tabela}.{coluna}"
    finally:
        motor.dispose()


def test_jsonb_preserva_dict_aninhado_com_unicode(sessao):
    from app.modelos import Analise

    parametros = {
        "duracao_maxima_s": 3600,
        "titulo": "ação — 日本語 😀",
        "aninhado": {"lista": [1, 2.5, {"a": None, "b": True}], "vazio": {}},
    }
    usuario = _criar_usuario(sessao)
    analise = _criar_analise(sessao, usuario.id, _criar_video(sessao, usuario.id).id, parametros)
    sessao.commit()
    sessao.expire_all()
    lido = sessao.execute(select(Analise.parametros).where(Analise.id == analise.id)).scalar_one()
    assert lido == parametros
