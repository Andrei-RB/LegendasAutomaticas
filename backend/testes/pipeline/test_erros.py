import dataclasses

import pytest
from celery.exceptions import SoftTimeLimitExceeded

from app.pipeline.armazenamento import CaminhoInvalido, ErroArmazenamento
from app.pipeline.erros import MENSAGENS, ErroPipeline, ErroPublico, traduzir
from app.pipeline.trava_gpu import TravaIndisponivel, TravaPerdida

CODIGOS = {
    "INTERNO",
    "ENTRADA_INVALIDA",
    "ENTRADA_AUSENTE",
    "ARMAZENAMENTO",
    "GPU_INDISPONIVEL",
    "TEMPO_ESGOTADO",
    "ETAPA_DESCONHECIDA",
    "ANALISE_INEXISTENTE",
}

TEXTOS_SENSIVEIS = [
    "/dados/x/y.mp4",
    "C:\\Usuarios\\exemplo\\video.mp4",
    "SELECT id, senha_hash FROM usuarios WHERE email = 'a@b.c'",
    "Traceback (most recent call last):",
    'File "/app/pipeline/executor.py", line 42',
    "segredo-super-sensivel-123",
    "postgresql://usuario:senhasecreta@db:5432/viraliza",
]


def _vazamento(texto: str) -> str:
    return " | ".join(TEXTOS_SENSIVEIS) + " | " + texto


# catálogo


def test_catalogo_tem_exatamente_os_codigos_previstos():
    assert set(MENSAGENS) == CODIGOS


def test_mensagens_sao_textos_nao_vazios_distintos_e_sem_placeholders():
    for codigo, mensagem in MENSAGENS.items():
        assert isinstance(mensagem, str), codigo
        assert mensagem.strip(), codigo
        assert "{" not in mensagem and "}" not in mensagem, codigo
        assert "%s" not in mensagem and "%(" not in mensagem, codigo
    assert len(set(MENSAGENS.values())) == len(MENSAGENS)


def test_mensagens_nao_expoem_o_proprio_codigo_nem_termos_tecnicos():
    for codigo, mensagem in MENSAGENS.items():
        assert codigo not in mensagem
        for proibido in ("Traceback", "Exception", "postgres", "redis"):
            assert proibido.lower() not in mensagem.lower(), (codigo, proibido)


def test_mensagens_estao_em_portugues_com_acentuacao():
    assert any(c in "ãõáéíóúâêôçà" for m in MENSAGENS.values() for c in m.lower())


# ErroPipeline


@pytest.mark.parametrize("codigo", sorted(CODIGOS))
def test_erro_pipeline_expoe_codigo_e_mensagem_do_catalogo(codigo):
    erro = ErroPipeline(codigo, "detalhe técnico")

    assert erro.codigo == codigo
    assert erro.mensagem == MENSAGENS[codigo]
    assert erro.detalhe == "detalhe técnico"


def test_erro_pipeline_detalhe_padrao_vazio():
    assert ErroPipeline("INTERNO").detalhe == ""


def test_str_do_erro_e_a_mensagem_e_nunca_o_detalhe():
    erro = ErroPipeline("ARMAZENAMENTO", "/dados/x/y.mp4 falhou: SELECT 1")

    assert str(erro) == MENSAGENS["ARMAZENAMENTO"]
    assert "/dados" not in str(erro)
    assert "SELECT" not in str(erro)


def test_erro_pipeline_e_excecao():
    with pytest.raises(ErroPipeline) as capturado:
        raise ErroPipeline("ENTRADA_AUSENTE")

    assert capturado.value.codigo == "ENTRADA_AUSENTE"


@pytest.mark.parametrize(
    "codigo",
    ["", "interno", "Interno", "CODIGO_NOVO", "INTERNO ", "INTERNO\n", "../../etc", "ENTRADA"],
)
def test_codigo_fora_do_catalogo_levanta_value_error(codigo):
    with pytest.raises(ValueError):
        ErroPipeline(codigo)


def test_erro_publico_e_imutavel():
    publico = ErroPublico(codigo="INTERNO", mensagem="m")

    assert publico.codigo == "INTERNO"
    assert publico.mensagem == "m"
    with pytest.raises(dataclasses.FrozenInstanceError):
        publico.codigo = "OUTRO"  # type: ignore[misc]


# traduzir


@pytest.mark.parametrize("codigo", sorted(CODIGOS))
def test_traduzir_erro_pipeline_preserva_o_codigo(codigo):
    publico = traduzir(ErroPipeline(codigo, _vazamento("x")))

    assert publico == ErroPublico(codigo=codigo, mensagem=MENSAGENS[codigo])


@pytest.mark.parametrize(
    ("fabrica", "esperado"),
    [
        (TravaIndisponivel, "GPU_INDISPONIVEL"),
        (TravaPerdida, "GPU_INDISPONIVEL"),
        (ErroArmazenamento, "ARMAZENAMENTO"),
        (CaminhoInvalido, "ARMAZENAMENTO"),
        (OSError, "ARMAZENAMENTO"),
        (FileNotFoundError, "ARMAZENAMENTO"),
        (PermissionError, "ARMAZENAMENTO"),
        (SoftTimeLimitExceeded, "TEMPO_ESGOTADO"),
        (TimeoutError, "TEMPO_ESGOTADO"),
        (RuntimeError, "INTERNO"),
        (ValueError, "INTERNO"),
        (KeyError, "INTERNO"),
        (ZeroDivisionError, "INTERNO"),
        (MemoryError, "INTERNO"),
        (Exception, "INTERNO"),
    ],
)
def test_traduzir_mapeia_tipo_para_codigo(fabrica, esperado):
    publico = traduzir(fabrica(_vazamento("falha")))

    assert publico.codigo == esperado
    assert publico.mensagem == MENSAGENS[esperado]


def test_timeout_error_tem_precedencia_sobre_oserror():
    assert issubclass(TimeoutError, OSError)

    assert traduzir(TimeoutError("lento")).codigo == "TEMPO_ESGOTADO"


@pytest.mark.parametrize(
    "fabrica",
    [
        TravaIndisponivel,
        TravaPerdida,
        ErroArmazenamento,
        CaminhoInvalido,
        OSError,
        SoftTimeLimitExceeded,
        TimeoutError,
        RuntimeError,
        ValueError,
        Exception,
        lambda texto: ErroPipeline("INTERNO", texto),
        lambda texto: ErroPipeline("ARMAZENAMENTO", texto),
    ],
)
@pytest.mark.parametrize("sensivel", TEXTOS_SENSIVEIS)
def test_traduzir_nunca_vaza_texto_da_excecao(fabrica, sensivel):
    publico = traduzir(fabrica(sensivel))

    assert sensivel not in publico.mensagem
    assert sensivel not in publico.codigo
    assert publico.mensagem == MENSAGENS[publico.codigo]


def test_traduzir_ignora_a_causa_encadeada():
    try:
        try:
            raise OSError("/dados/x/y.mp4: permissão negada")
        except OSError as causa:
            raise ErroPipeline("ARMAZENAMENTO", "detalhe") from causa
    except ErroPipeline as erro:
        publico = traduzir(erro)

    assert publico.mensagem == MENSAGENS["ARMAZENAMENTO"]
    assert "permissão negada" not in publico.mensagem


def test_traduzir_oserror_com_errno_e_nome_de_arquivo_nao_vaza_o_caminho():
    erro = FileNotFoundError(2, "No such file or directory", "/dados/u/v/saida.json")

    publico = traduzir(erro)

    assert publico.codigo == "ARMAZENAMENTO"
    assert "/dados" not in publico.mensagem
    assert "saida.json" not in publico.mensagem


def test_traduzir_excecao_com_str_quebrado_nao_levanta():
    class Estranha(Exception):
        def __str__(self):
            raise RuntimeError("str quebrado")

    assert traduzir(Estranha()).codigo == "INTERNO"
