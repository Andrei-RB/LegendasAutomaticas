"""Esquema inicial."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GATILHO_FUNCAO = """
CREATE FUNCTION exportacoes_validar_modelo_dono() RETURNS trigger LANGUAGE plpgsql
SET search_path = public, pg_temp AS $$
BEGIN
    IF NEW.modelo_legenda_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM modelos_legenda m
        WHERE m.id = NEW.modelo_legenda_id AND (m.user_id IS NULL OR m.user_id = NEW.user_id)
    ) THEN
        RAISE EXCEPTION 'modelo de legenda pertence a outro usuário'
            USING ERRCODE = '23503', CONSTRAINT = 'ck_exportacoes_modelo_dono';
    END IF;
    RETURN NEW;
END;
$$
"""
GATILHO_IMUTAVEL_FUNCAO = """
CREATE FUNCTION modelos_legenda_user_id_imutavel() RETURNS trigger LANGUAGE plpgsql
SET search_path = public, pg_temp AS $$
BEGIN
    RAISE EXCEPTION 'o dono do modelo de legenda não pode mudar'
        USING ERRCODE = '23514', CONSTRAINT = 'ck_modelos_legenda_user_id_imutavel';
END;
$$
"""
GATILHO_IMUTAVEL = """
CREATE TRIGGER ck_modelos_legenda_user_id_imutavel
BEFORE UPDATE OF user_id ON modelos_legenda
FOR EACH ROW WHEN (OLD.user_id IS DISTINCT FROM NEW.user_id)
EXECUTE FUNCTION modelos_legenda_user_id_imutavel()
"""
GATILHO = """
CREATE TRIGGER ck_exportacoes_modelo_dono
BEFORE INSERT OR UPDATE OF modelo_legenda_id, user_id ON exportacoes
FOR EACH ROW EXECUTE FUNCTION exportacoes_validar_modelo_dono()
"""


def upgrade() -> None:
    op.create_table(
        "cache_hashtags",
        sa.Column("nicho", sa.String(length=64), nullable=False),
        sa.Column("plataforma", sa.String(length=16), nullable=False),
        sa.Column(
            "hashtags",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "buscado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cache_hashtags")),
        sa.UniqueConstraint("nicho", "plataforma", name=op.f("uq_cache_hashtags_nicho_plataforma")),
    )
    op.create_table(
        "usuarios",
        sa.Column("nome_usuario", sa.String(length=64), nullable=False),
        sa.Column("idioma", sa.String(length=10), server_default="pt-BR", nullable=False),
        sa.Column("ativo", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_usuarios")),
        sa.UniqueConstraint("nome_usuario", name=op.f("uq_usuarios_nome_usuario")),
    )
    op.create_table(
        "fontes",
        sa.Column("familia", sa.String(length=64), nullable=False),
        sa.Column("origem", sa.String(length=16), nullable=False),
        sa.Column("caminho", sa.Text(), nullable=False),
        sa.Column("licenca", sa.String(length=64), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["usuarios.id"],
            name=op.f("fk_fontes_user_id_usuarios"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_fontes")),
    )
    op.create_index(op.f("ix_fontes_user_id"), "fontes", ["user_id"], unique=False)
    op.create_table(
        "hashtags_usuario",
        sa.Column("hashtag", sa.String(length=64), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["usuarios.id"],
            name=op.f("fk_hashtags_usuario_user_id_usuarios"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_hashtags_usuario")),
        sa.UniqueConstraint("user_id", "hashtag", name=op.f("uq_hashtags_usuario_user_id_hashtag")),
    )
    op.create_index(
        op.f("ix_hashtags_usuario_user_id"), "hashtags_usuario", ["user_id"], unique=False
    )
    op.create_table(
        "modelos_legenda",
        sa.Column("nome", sa.String(length=64), nullable=False),
        sa.Column("versao_schema", sa.Integer(), server_default="1", nullable=False),
        sa.Column("especificacao", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["usuarios.id"],
            name=op.f("fk_modelos_legenda_user_id_usuarios"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_modelos_legenda")),
    )
    op.create_index(
        op.f("ix_modelos_legenda_user_id"), "modelos_legenda", ["user_id"], unique=False
    )
    op.create_table(
        "videos",
        sa.Column("origem", sa.String(length=16), nullable=False),
        sa.Column("url_origem", sa.Text(), nullable=True),
        sa.Column("caminho_original", sa.Text(), nullable=False),
        sa.Column("caminho_proxy", sa.Text(), nullable=True),
        sa.Column("duracao_s", sa.Float(), nullable=True),
        sa.Column(
            "metadados",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("perfil", sa.String(length=32), nullable=True),
        sa.Column(
            "expira_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now() + interval '7 days'"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["usuarios.id"],
            name=op.f("fk_videos_user_id_usuarios"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_videos")),
        sa.UniqueConstraint("id", "user_id", name=op.f("uq_videos_id_user_id")),
    )
    op.create_index(op.f("ix_videos_user_id"), "videos", ["user_id"], unique=False)
    op.create_table(
        "analises",
        sa.Column("video_id", sa.Uuid(), nullable=False),
        sa.Column("parametros", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="pendente", nullable=False),
        sa.Column("etapa_atual", sa.String(length=32), nullable=True),
        sa.Column("progresso", sa.Float(), server_default="0", nullable=False),
        sa.Column("erro_amigavel", sa.Text(), nullable=True),
        sa.Column(
            "atualizado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "progresso >= 0 AND progresso <= 100", name=op.f("ck_analises_progresso_faixa")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["usuarios.id"],
            name=op.f("fk_analises_user_id_usuarios"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["video_id", "user_id"],
            ["videos.id", "videos.user_id"],
            name=op.f("fk_analises_video_id_videos"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analises")),
        sa.UniqueConstraint("id", "user_id", name=op.f("uq_analises_id_user_id")),
    )
    op.create_index(op.f("ix_analises_user_id"), "analises", ["user_id"], unique=False)
    op.create_index(op.f("ix_analises_video_id"), "analises", ["video_id"], unique=False)
    op.create_table(
        "candidatos",
        sa.Column("analise_id", sa.Uuid(), nullable=False),
        sa.Column("inicio_s", sa.Float(), nullable=False),
        sa.Column("fim_s", sa.Float(), nullable=False),
        sa.Column("id_frase_inicial", sa.Integer(), nullable=False),
        sa.Column("id_frase_final", sa.Integer(), nullable=False),
        sa.Column(
            "variantes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("nota_heuristica", sa.Float(), nullable=True),
        sa.Column(
            "features",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("fim_s > inicio_s", name=op.f("ck_candidatos_intervalo_valido")),
        sa.ForeignKeyConstraint(
            ["analise_id", "user_id"],
            ["analises.id", "analises.user_id"],
            name=op.f("fk_candidatos_analise_id_analises"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["usuarios.id"],
            name=op.f("fk_candidatos_user_id_usuarios"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_candidatos")),
        sa.UniqueConstraint("id", "user_id", name=op.f("uq_candidatos_id_user_id")),
    )
    op.create_index(op.f("ix_candidatos_analise_id"), "candidatos", ["analise_id"], unique=False)
    op.create_index(op.f("ix_candidatos_user_id"), "candidatos", ["user_id"], unique=False)
    op.create_table(
        "chamadas_ia",
        sa.Column("analise_id", sa.Uuid(), nullable=True),
        sa.Column("tarefa", sa.String(length=32), nullable=False),
        sa.Column("provedor", sa.String(length=32), nullable=False),
        sa.Column("modelo", sa.String(length=64), nullable=False),
        sa.Column("tokens_entrada", sa.Integer(), server_default="0", nullable=False),
        sa.Column("tokens_saida", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "custo_usd", sa.Numeric(precision=12, scale=6), server_default="0", nullable=False
        ),
        sa.Column("latencia_ms", sa.Integer(), nullable=True),
        sa.Column("cache", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["analise_id", "user_id"],
            ["analises.id", "analises.user_id"],
            name=op.f("fk_chamadas_ia_analise_id_analises"),
            ondelete="SET NULL (analise_id)",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["usuarios.id"],
            name=op.f("fk_chamadas_ia_user_id_usuarios"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chamadas_ia")),
    )
    op.create_index(op.f("ix_chamadas_ia_analise_id"), "chamadas_ia", ["analise_id"], unique=False)
    op.create_index(op.f("ix_chamadas_ia_user_id"), "chamadas_ia", ["user_id"], unique=False)
    op.create_table(
        "execucoes_etapa",
        sa.Column("analise_id", sa.Uuid(), nullable=False),
        sa.Column("etapa", sa.String(length=32), nullable=False),
        sa.Column("hash_entrada", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="pendente", nullable=False),
        sa.Column(
            "artefatos",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "metricas",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("iniciado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("concluido_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["analise_id", "user_id"],
            ["analises.id", "analises.user_id"],
            name=op.f("fk_execucoes_etapa_analise_id_analises"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["usuarios.id"],
            name=op.f("fk_execucoes_etapa_user_id_usuarios"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_execucoes_etapa")),
        sa.UniqueConstraint(
            "analise_id",
            "etapa",
            "hash_entrada",
            name=op.f("uq_execucoes_etapa_analise_id_etapa_hash_entrada"),
        ),
    )
    op.create_index(
        op.f("ix_execucoes_etapa_analise_id"), "execucoes_etapa", ["analise_id"], unique=False
    )
    op.create_index(
        op.f("ix_execucoes_etapa_user_id"), "execucoes_etapa", ["user_id"], unique=False
    )
    op.create_table(
        "cortes",
        sa.Column("analise_id", sa.Uuid(), nullable=False),
        sa.Column("candidato_id", sa.Uuid(), nullable=True),
        sa.Column("inicio_s", sa.Float(), nullable=False),
        sa.Column("fim_s", sa.Float(), nullable=False),
        sa.Column("formato", sa.String(length=16), server_default="9:16", nullable=False),
        sa.Column(
            "keyframes_camera",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("caminho_previa", sa.Text(), nullable=True),
        sa.Column("caminho_final", sa.Text(), nullable=True),
        sa.Column(
            "expira_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now() + interval '30 days'"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("fim_s > inicio_s", name=op.f("ck_cortes_intervalo_valido")),
        sa.ForeignKeyConstraint(
            ["analise_id", "user_id"],
            ["analises.id", "analises.user_id"],
            name=op.f("fk_cortes_analise_id_analises"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["candidato_id", "user_id"],
            ["candidatos.id", "candidatos.user_id"],
            name=op.f("fk_cortes_candidato_id_candidatos"),
            ondelete="SET NULL (candidato_id)",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["usuarios.id"],
            name=op.f("fk_cortes_user_id_usuarios"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cortes")),
        sa.UniqueConstraint("id", "user_id", name=op.f("uq_cortes_id_user_id")),
    )
    op.create_index(op.f("ix_cortes_analise_id"), "cortes", ["analise_id"], unique=False)
    op.create_index(op.f("ix_cortes_candidato_id"), "cortes", ["candidato_id"], unique=False)
    op.create_index(op.f("ix_cortes_user_id"), "cortes", ["user_id"], unique=False)
    op.create_table(
        "julgamentos",
        sa.Column("candidato_id", sa.Uuid(), nullable=False),
        sa.Column("juiz", sa.String(length=32), nullable=False),
        sa.Column("modelo", sa.String(length=64), nullable=False),
        sa.Column("versao_prompt", sa.String(length=16), nullable=False),
        sa.Column(
            "notas",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("motivo", sa.Text(), nullable=True),
        sa.Column(
            "citacoes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("valido", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["candidato_id", "user_id"],
            ["candidatos.id", "candidatos.user_id"],
            name=op.f("fk_julgamentos_candidato_id_candidatos"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["usuarios.id"],
            name=op.f("fk_julgamentos_user_id_usuarios"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_julgamentos")),
    )
    op.create_index(
        op.f("ix_julgamentos_candidato_id"), "julgamentos", ["candidato_id"], unique=False
    )
    op.create_index(op.f("ix_julgamentos_user_id"), "julgamentos", ["user_id"], unique=False)
    op.create_table(
        "documentos_legenda",
        sa.Column("corte_id", sa.Uuid(), nullable=False),
        sa.Column("versao", sa.Integer(), server_default="1", nullable=False),
        sa.Column("conteudo", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["corte_id", "user_id"],
            ["cortes.id", "cortes.user_id"],
            name=op.f("fk_documentos_legenda_corte_id_cortes"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["usuarios.id"],
            name=op.f("fk_documentos_legenda_user_id_usuarios"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_documentos_legenda")),
        sa.UniqueConstraint(
            "corte_id", "versao", name=op.f("uq_documentos_legenda_corte_id_versao")
        ),
        sa.UniqueConstraint("id", "user_id", name=op.f("uq_documentos_legenda_id_user_id")),
    )
    op.create_index(
        op.f("ix_documentos_legenda_corte_id"), "documentos_legenda", ["corte_id"], unique=False
    )
    op.create_index(
        op.f("ix_documentos_legenda_user_id"), "documentos_legenda", ["user_id"], unique=False
    )
    op.create_table(
        "feedback",
        sa.Column("corte_id", sa.Uuid(), nullable=True),
        sa.Column("candidato_id", sa.Uuid(), nullable=True),
        sa.Column("aprovado", sa.Boolean(), nullable=False),
        sa.Column("motivo", sa.Text(), nullable=True),
        sa.Column(
            "instantaneo",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["candidato_id", "user_id"],
            ["candidatos.id", "candidatos.user_id"],
            name=op.f("fk_feedback_candidato_id_candidatos"),
            ondelete="SET NULL (candidato_id)",
        ),
        sa.ForeignKeyConstraint(
            ["corte_id", "user_id"],
            ["cortes.id", "cortes.user_id"],
            name=op.f("fk_feedback_corte_id_cortes"),
            ondelete="SET NULL (corte_id)",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["usuarios.id"],
            name=op.f("fk_feedback_user_id_usuarios"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_feedback")),
    )
    op.create_index(op.f("ix_feedback_candidato_id"), "feedback", ["candidato_id"], unique=False)
    op.create_index(op.f("ix_feedback_corte_id"), "feedback", ["corte_id"], unique=False)
    op.create_index(op.f("ix_feedback_user_id"), "feedback", ["user_id"], unique=False)
    op.create_table(
        "textos_postagem",
        sa.Column("corte_id", sa.Uuid(), nullable=False),
        sa.Column("plataforma", sa.String(length=16), nullable=False),
        sa.Column("titulo", sa.Text(), nullable=True),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column(
            "hashtags",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "tags",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "capitulos",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["corte_id", "user_id"],
            ["cortes.id", "cortes.user_id"],
            name=op.f("fk_textos_postagem_corte_id_cortes"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["usuarios.id"],
            name=op.f("fk_textos_postagem_user_id_usuarios"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_textos_postagem")),
    )
    op.create_index(
        op.f("ix_textos_postagem_corte_id"), "textos_postagem", ["corte_id"], unique=False
    )
    op.create_index(
        op.f("ix_textos_postagem_user_id"), "textos_postagem", ["user_id"], unique=False
    )
    op.create_table(
        "exportacoes",
        sa.Column("corte_id", sa.Uuid(), nullable=False),
        sa.Column("modelo_legenda_id", sa.Uuid(), nullable=True),
        sa.Column("documento_legenda_id", sa.Uuid(), nullable=True),
        sa.Column(
            "caminhos_srt",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("caminho_mp4", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="pendente", nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["corte_id", "user_id"],
            ["cortes.id", "cortes.user_id"],
            name=op.f("fk_exportacoes_corte_id_cortes"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["documento_legenda_id", "user_id"],
            ["documentos_legenda.id", "documentos_legenda.user_id"],
            name=op.f("fk_exportacoes_documento_legenda_id_documentos_legenda"),
            ondelete="SET NULL (documento_legenda_id)",
        ),
        sa.ForeignKeyConstraint(
            ["modelo_legenda_id"],
            ["modelos_legenda.id"],
            name=op.f("fk_exportacoes_modelo_legenda_id_modelos_legenda"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["usuarios.id"],
            name=op.f("fk_exportacoes_user_id_usuarios"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exportacoes")),
    )
    op.create_index(op.f("ix_exportacoes_corte_id"), "exportacoes", ["corte_id"], unique=False)
    op.create_index(
        op.f("ix_exportacoes_documento_legenda_id"),
        "exportacoes",
        ["documento_legenda_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_exportacoes_modelo_legenda_id"), "exportacoes", ["modelo_legenda_id"], unique=False
    )
    op.create_index(op.f("ix_exportacoes_user_id"), "exportacoes", ["user_id"], unique=False)

    op.execute(GATILHO_FUNCAO)
    op.execute(GATILHO)
    op.execute(GATILHO_IMUTAVEL_FUNCAO)
    op.execute(GATILHO_IMUTAVEL)


def downgrade() -> None:
    op.execute("DROP TRIGGER ck_modelos_legenda_user_id_imutavel ON modelos_legenda")
    op.execute("DROP FUNCTION modelos_legenda_user_id_imutavel()")
    op.execute("DROP TRIGGER ck_exportacoes_modelo_dono ON exportacoes")
    op.execute("DROP FUNCTION exportacoes_validar_modelo_dono()")
    op.drop_index(op.f("ix_exportacoes_user_id"), table_name="exportacoes")
    op.drop_index(op.f("ix_exportacoes_modelo_legenda_id"), table_name="exportacoes")
    op.drop_index(op.f("ix_exportacoes_documento_legenda_id"), table_name="exportacoes")
    op.drop_index(op.f("ix_exportacoes_corte_id"), table_name="exportacoes")
    op.drop_table("exportacoes")
    op.drop_index(op.f("ix_textos_postagem_user_id"), table_name="textos_postagem")
    op.drop_index(op.f("ix_textos_postagem_corte_id"), table_name="textos_postagem")
    op.drop_table("textos_postagem")
    op.drop_index(op.f("ix_feedback_user_id"), table_name="feedback")
    op.drop_index(op.f("ix_feedback_corte_id"), table_name="feedback")
    op.drop_index(op.f("ix_feedback_candidato_id"), table_name="feedback")
    op.drop_table("feedback")
    op.drop_index(op.f("ix_documentos_legenda_user_id"), table_name="documentos_legenda")
    op.drop_index(op.f("ix_documentos_legenda_corte_id"), table_name="documentos_legenda")
    op.drop_table("documentos_legenda")
    op.drop_index(op.f("ix_julgamentos_user_id"), table_name="julgamentos")
    op.drop_index(op.f("ix_julgamentos_candidato_id"), table_name="julgamentos")
    op.drop_table("julgamentos")
    op.drop_index(op.f("ix_cortes_user_id"), table_name="cortes")
    op.drop_index(op.f("ix_cortes_candidato_id"), table_name="cortes")
    op.drop_index(op.f("ix_cortes_analise_id"), table_name="cortes")
    op.drop_table("cortes")
    op.drop_index(op.f("ix_execucoes_etapa_user_id"), table_name="execucoes_etapa")
    op.drop_index(op.f("ix_execucoes_etapa_analise_id"), table_name="execucoes_etapa")
    op.drop_table("execucoes_etapa")
    op.drop_index(op.f("ix_chamadas_ia_user_id"), table_name="chamadas_ia")
    op.drop_index(op.f("ix_chamadas_ia_analise_id"), table_name="chamadas_ia")
    op.drop_table("chamadas_ia")
    op.drop_index(op.f("ix_candidatos_user_id"), table_name="candidatos")
    op.drop_index(op.f("ix_candidatos_analise_id"), table_name="candidatos")
    op.drop_table("candidatos")
    op.drop_index(op.f("ix_analises_video_id"), table_name="analises")
    op.drop_index(op.f("ix_analises_user_id"), table_name="analises")
    op.drop_table("analises")
    op.drop_index(op.f("ix_videos_user_id"), table_name="videos")
    op.drop_table("videos")
    op.drop_index(op.f("ix_modelos_legenda_user_id"), table_name="modelos_legenda")
    op.drop_table("modelos_legenda")
    op.drop_index(op.f("ix_hashtags_usuario_user_id"), table_name="hashtags_usuario")
    op.drop_table("hashtags_usuario")
    op.drop_index(op.f("ix_fontes_user_id"), table_name="fontes")
    op.drop_table("fontes")
    op.drop_table("usuarios")
    op.drop_table("cache_hashtags")
