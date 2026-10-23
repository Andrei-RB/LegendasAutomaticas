import dataclasses
import hashlib
import os
import stat
import threading
import uuid

import pytest

from app.pipeline.armazenamento import (
    ArmazenamentoLocal,
    ArtefatoGravado,
    CaminhoInvalido,
    ErroArmazenamento,
    GravacaoAtomica,
)

POSIX = os.name == "posix"
USUARIO = uuid.UUID("11111111-1111-4111-8111-111111111111")
VIDEO = uuid.UUID("22222222-2222-4222-8222-222222222222")
OUTRO_USUARIO = uuid.UUID("33333333-3333-4333-8333-333333333333")


@pytest.fixture
def raiz(tmp_path):
    return tmp_path / "dados"


@pytest.fixture
def armazem(raiz):
    return ArmazenamentoLocal(raiz)


def _symlink(origem, destino, *, diretorio=False):
    try:
        os.symlink(origem, destino, target_is_directory=diretorio)
    except (OSError, NotImplementedError):
        pytest.skip("symlink indisponível neste ambiente")


def _sha(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()


def _arquivos(pasta):
    return sorted(p.name for p in pasta.iterdir())


OPERACOES = {
    "gravar": lambda a, u, v, n: a.gravar(u, v, n, b"x"),
    "gravacao_atomica": lambda a, u, v, n: a.gravacao_atomica(u, v, n).__enter__(),
    "ler": lambda a, u, v, n: a.ler(u, v, n),
    "caminho": lambda a, u, v, n: a.caminho(u, v, n),
    "existe": lambda a, u, v, n: a.existe(u, v, n),
    "remover": lambda a, u, v, n: a.remover(u, v, n),
    "verificar": lambda a, u, v, n: a.verificar(u, v, n, "0" * 64),
}

NOMES_MALICIOSOS = [
    "..",
    ".",
    "",
    "/abs",
    "/etc/passwd",
    "a\\b",
    "..\\x",
    "a/../b",
    "../x",
    "a/..",
    "a//b",
    "a/",
    "/",
    "x\x00.json",
    "\x00",
    "a" * 129,
    "con:",
    "com espaço.json",
    " x",
    "x ",
    ".oculto",
    "-inicio",
    "_inicio",
    "a/b/c/d",
    "a/./b",
    "C:\\Windows\\x",
    "x\n.json",
    "x.json\n",
    "ação.json",
    "a/.b",
    "x;rm.json",
    "x$(id).json",
]


# caminho feliz


def test_gravar_devolve_artefato_com_nome_hash_e_tamanho(armazem):
    dados = "conteúdo é ação".encode()

    artefato = armazem.gravar(USUARIO, VIDEO, "saida.json", dados)

    assert artefato == ArtefatoGravado(nome="saida.json", sha256=_sha(dados), bytes=len(dados))


def test_layout_usuario_video_nome(armazem, raiz):
    armazem.gravar(USUARIO, VIDEO, "saida.json", b"abc")

    assert (raiz / str(USUARIO) / str(VIDEO) / "saida.json").read_bytes() == b"abc"


def test_ler_devolve_o_que_foi_gravado(armazem):
    armazem.gravar(USUARIO, VIDEO, "a.bin", bytes(range(256)))

    assert armazem.ler(USUARIO, VIDEO, "a.bin") == bytes(range(256))


def test_gravar_vazio(armazem):
    artefato = armazem.gravar(USUARIO, VIDEO, "vazio.bin", b"")

    assert artefato.bytes == 0
    assert artefato.sha256 == _sha(b"")
    assert armazem.ler(USUARIO, VIDEO, "vazio.bin") == b""


def test_caminho_aponta_para_o_arquivo_dentro_da_raiz(armazem, raiz):
    armazem.gravar(USUARIO, VIDEO, "a.json", b"1")

    caminho = armazem.caminho(USUARIO, VIDEO, "a.json")

    assert caminho.read_bytes() == b"1"
    assert caminho.resolve().is_relative_to(raiz.resolve())


def test_existe_reflete_o_disco(armazem):
    assert not armazem.existe(USUARIO, VIDEO, "a.json")

    armazem.gravar(USUARIO, VIDEO, "a.json", b"1")

    assert armazem.existe(USUARIO, VIDEO, "a.json")
    assert not armazem.existe(USUARIO, VIDEO, "b.json")


def test_verificar_true_para_hash_correto(armazem):
    armazem.gravar(USUARIO, VIDEO, "a.json", b"conteudo")

    assert armazem.verificar(USUARIO, VIDEO, "a.json", _sha(b"conteudo")) is True


def test_verificar_false_para_hash_divergente_e_arquivo_ausente(armazem):
    armazem.gravar(USUARIO, VIDEO, "a.json", b"conteudo")

    assert armazem.verificar(USUARIO, VIDEO, "a.json", _sha(b"outro")) is False
    assert armazem.verificar(USUARIO, VIDEO, "ausente.json", _sha(b"conteudo")) is False


def test_verificar_detecta_adulteracao_externa(armazem, raiz):
    artefato = armazem.gravar(USUARIO, VIDEO, "a.json", b"original")
    (raiz / str(USUARIO) / str(VIDEO) / "a.json").write_bytes(b"adulterado")

    assert armazem.verificar(USUARIO, VIDEO, "a.json", artefato.sha256) is False


def test_subpastas_ate_tres_segmentos(armazem, raiz):
    armazem.gravar(USUARIO, VIDEO, "a/b/c.json", b"1")

    assert armazem.ler(USUARIO, VIDEO, "a/b/c.json") == b"1"
    assert (raiz / str(USUARIO) / str(VIDEO) / "a" / "b" / "c.json").is_file()


@pytest.mark.parametrize("nome", ["a", "A.b_c-d.json", "0", "a/b", "v1.2/saida_3.srt"])
def test_nomes_validos_aceitos(armazem, nome):
    armazem.gravar(USUARIO, VIDEO, nome, b"1")

    assert armazem.ler(USUARIO, VIDEO, nome) == b"1"


def test_gravar_sobre_existente_substitui(armazem, raiz):
    armazem.gravar(USUARIO, VIDEO, "a.json", b"antigo")

    artefato = armazem.gravar(USUARIO, VIDEO, "a.json", b"novo")

    assert armazem.ler(USUARIO, VIDEO, "a.json") == b"novo"
    assert artefato.sha256 == _sha(b"novo")
    assert _arquivos(raiz / str(USUARIO) / str(VIDEO)) == ["a.json"]


def test_isolamento_entre_usuarios_e_videos(armazem):
    armazem.gravar(USUARIO, VIDEO, "a.json", b"do-usuario")

    assert not armazem.existe(OUTRO_USUARIO, VIDEO, "a.json")
    assert not armazem.existe(USUARIO, uuid.uuid4(), "a.json")
    armazem.gravar(OUTRO_USUARIO, VIDEO, "a.json", b"do-outro")
    assert armazem.ler(USUARIO, VIDEO, "a.json") == b"do-usuario"
    assert armazem.ler(OUTRO_USUARIO, VIDEO, "a.json") == b"do-outro"


def test_remover_apaga_o_arquivo_e_ignora_o_ausente(armazem):
    armazem.gravar(USUARIO, VIDEO, "a.json", b"1")

    armazem.remover(USUARIO, VIDEO, "a.json")
    armazem.remover(USUARIO, VIDEO, "a.json")
    armazem.remover(USUARIO, VIDEO, "pasta/nunca-existiu.json")

    assert not armazem.existe(USUARIO, VIDEO, "a.json")


def test_remover_nao_afeta_outro_usuario(armazem):
    armazem.gravar(USUARIO, VIDEO, "a.json", b"1")
    armazem.gravar(OUTRO_USUARIO, VIDEO, "a.json", b"2")

    armazem.remover(USUARIO, VIDEO, "a.json")

    assert armazem.ler(OUTRO_USUARIO, VIDEO, "a.json") == b"2"


def test_ler_recusa_arquivo_acima_do_limite(armazem, monkeypatch):
    armazem.gravar(USUARIO, VIDEO, "grande.bin", b"x" * 10)
    monkeypatch.setattr("app.pipeline.armazenamento.LIMITE_LEITURA_BYTES", 5)

    with pytest.raises(ErroArmazenamento):
        armazem.ler(USUARIO, VIDEO, "grande.bin")


def test_ler_arquivo_ausente_falha(armazem):
    with pytest.raises((ErroArmazenamento, FileNotFoundError)):
        armazem.ler(USUARIO, VIDEO, "nao-existe.json")


def test_artefato_gravado_e_imutavel():
    artefato = ArtefatoGravado(nome="a", sha256="0" * 64, bytes=1)

    with pytest.raises(dataclasses.FrozenInstanceError):
        artefato.nome = "b"  # type: ignore[misc]


def test_caminho_invalido_e_erro_de_armazenamento():
    assert issubclass(CaminhoInvalido, ErroArmazenamento)
    assert issubclass(ErroArmazenamento, Exception)


# modo de acesso


@pytest.mark.skipif(not POSIX, reason="permissões POSIX")
def test_diretorios_0700_e_arquivos_0600(armazem, raiz):
    armazem.gravar(USUARIO, VIDEO, "sub/a.json", b"1")

    base = raiz / str(USUARIO)
    for pasta in (base, base / str(VIDEO), base / str(VIDEO) / "sub"):
        assert stat.S_IMODE(pasta.stat().st_mode) == 0o700
    assert stat.S_IMODE((base / str(VIDEO) / "sub" / "a.json").stat().st_mode) == 0o600


# validação de entradas


@pytest.mark.parametrize("operacao", list(OPERACOES))
@pytest.mark.parametrize("nome", NOMES_MALICIOSOS)
def test_nome_invalido_rejeitado_em_toda_operacao(armazem, raiz, operacao, nome):
    with pytest.raises(CaminhoInvalido):
        OPERACOES[operacao](armazem, USUARIO, VIDEO, nome)

    assert not raiz.exists() or list(raiz.rglob("*")) == []


@pytest.mark.parametrize("operacao", list(OPERACOES))
@pytest.mark.parametrize(
    "identificador",
    [
        "..",
        "../..",
        str(USUARIO),
        "11111111-1111-4111-8111-111111111111/../x",
        "",
        None,
        123,
        b"1111",
        object(),
    ],
    ids=[
        "ponto_ponto",
        "sobe_dois",
        "uuid_em_str",
        "uuid_com_traversal",
        "vazio",
        "none",
        "int",
        "bytes",
        "objeto",
    ],
)
def test_user_id_que_nao_e_uuid_rejeitado(armazem, raiz, operacao, identificador):
    with pytest.raises(CaminhoInvalido):
        OPERACOES[operacao](armazem, identificador, VIDEO, "a.json")

    assert not raiz.exists() or list(raiz.rglob("*")) == []


@pytest.mark.parametrize("operacao", list(OPERACOES))
@pytest.mark.parametrize("identificador", ["..", str(VIDEO), "x/../..", None, 7])
def test_video_id_que_nao_e_uuid_rejeitado(armazem, raiz, operacao, identificador):
    with pytest.raises(CaminhoInvalido):
        OPERACOES[operacao](armazem, USUARIO, identificador, "a.json")

    assert not raiz.exists() or list(raiz.rglob("*")) == []


def test_nome_com_128_caracteres_aceito_e_129_rejeitado(armazem):
    assert armazem.caminho(USUARIO, VIDEO, "x" * 128).name == "x" * 128

    with pytest.raises(CaminhoInvalido):
        armazem.caminho(USUARIO, VIDEO, "x" * 129)
    with pytest.raises(CaminhoInvalido):
        armazem.gravar(USUARIO, VIDEO, "x" * 129, b"1")


def test_segmento_longo_dentro_de_subpasta_rejeitado(armazem):
    with pytest.raises(CaminhoInvalido):
        armazem.gravar(USUARIO, VIDEO, "a/" + "x" * 129, b"1")


# symlinks


def test_destino_symlink_para_fora_rejeitado_e_alvo_intacto(armazem, raiz, tmp_path):
    armazem.gravar(USUARIO, VIDEO, "ok.json", b"1")
    alvo = tmp_path / "segredo.txt"
    alvo.write_bytes(b"segredo")
    _symlink(alvo, raiz / str(USUARIO) / str(VIDEO) / "link.json")

    with pytest.raises(CaminhoInvalido):
        armazem.gravar(USUARIO, VIDEO, "link.json", b"sobrescrito")
    with pytest.raises(CaminhoInvalido):
        armazem.ler(USUARIO, VIDEO, "link.json")
    with pytest.raises(CaminhoInvalido):
        armazem.existe(USUARIO, VIDEO, "link.json")
    with pytest.raises(CaminhoInvalido):
        armazem.verificar(USUARIO, VIDEO, "link.json", _sha(b"segredo"))
    with pytest.raises(CaminhoInvalido):
        armazem.caminho(USUARIO, VIDEO, "link.json")

    assert alvo.read_bytes() == b"segredo"


def test_destino_symlink_para_arquivo_dentro_da_raiz_rejeitado(armazem, raiz):
    armazem.gravar(USUARIO, VIDEO, "real.json", b"real")
    _symlink(
        raiz / str(USUARIO) / str(VIDEO) / "real.json", raiz / str(USUARIO) / str(VIDEO) / "l.json"
    )

    with pytest.raises(CaminhoInvalido):
        armazem.ler(USUARIO, VIDEO, "l.json")
    with pytest.raises(CaminhoInvalido):
        armazem.gravar(USUARIO, VIDEO, "l.json", b"novo")

    assert armazem.ler(USUARIO, VIDEO, "real.json") == b"real"


def test_destino_symlink_quebrado_rejeitado(armazem, raiz, tmp_path):
    armazem.gravar(USUARIO, VIDEO, "ok.json", b"1")
    alvo = tmp_path / "ainda-nao-existe.txt"
    _symlink(alvo, raiz / str(USUARIO) / str(VIDEO) / "quebrado.json")

    with pytest.raises(CaminhoInvalido):
        armazem.gravar(USUARIO, VIDEO, "quebrado.json", b"x")

    assert not alvo.exists()


def test_diretorio_do_usuario_symlink_para_fora_rejeitado(armazem, raiz, tmp_path):
    fora = tmp_path / "fora"
    fora.mkdir()
    raiz.mkdir()
    _symlink(fora, raiz / str(USUARIO), diretorio=True)

    with pytest.raises(CaminhoInvalido):
        armazem.gravar(USUARIO, VIDEO, "a.json", b"x")
    with pytest.raises(CaminhoInvalido):
        armazem.ler(USUARIO, VIDEO, "a.json")
    with pytest.raises(CaminhoInvalido):
        armazem.existe(USUARIO, VIDEO, "a.json")

    assert list(fora.iterdir()) == []


def test_diretorio_do_video_symlink_para_fora_rejeitado(armazem, raiz, tmp_path):
    fora = tmp_path / "fora"
    fora.mkdir()
    (fora / "a.json").write_bytes(b"alheio")
    (raiz / str(USUARIO)).mkdir(parents=True)
    _symlink(fora, raiz / str(USUARIO) / str(VIDEO), diretorio=True)

    with pytest.raises(CaminhoInvalido):
        armazem.gravar(USUARIO, VIDEO, "novo.json", b"x")
    with pytest.raises(CaminhoInvalido):
        armazem.ler(USUARIO, VIDEO, "a.json")
    with pytest.raises(CaminhoInvalido):
        armazem.caminho(USUARIO, VIDEO, "a.json")

    assert _arquivos(fora) == ["a.json"]


def test_diretorio_do_video_symlink_para_dentro_da_raiz_rejeitado(armazem, raiz):
    armazem.gravar(USUARIO, OUTRO_USUARIO, "a.json", b"1")
    _symlink(
        raiz / str(USUARIO) / str(OUTRO_USUARIO),
        raiz / str(USUARIO) / str(VIDEO),
        diretorio=True,
    )

    with pytest.raises(CaminhoInvalido):
        armazem.ler(USUARIO, VIDEO, "a.json")


def test_subdiretorio_symlink_para_fora_rejeitado(armazem, raiz, tmp_path):
    fora = tmp_path / "fora"
    fora.mkdir()
    armazem.gravar(USUARIO, VIDEO, "ok.json", b"1")
    _symlink(fora, raiz / str(USUARIO) / str(VIDEO) / "sub", diretorio=True)

    with pytest.raises(CaminhoInvalido):
        armazem.gravar(USUARIO, VIDEO, "sub/a.json", b"x")

    assert list(fora.iterdir()) == []


# gravação atômica e falhas


def test_gravacao_atomica_usa_temporario_no_diretorio_do_destino(armazem, raiz):
    pasta = raiz / str(USUARIO) / str(VIDEO)

    with armazem.gravacao_atomica(USUARIO, VIDEO, "saida.mp4") as grav:
        assert isinstance(grav, GravacaoAtomica)
        assert grav.caminho.parent == pasta
        assert grav.caminho.name != "saida.mp4"
        grav.caminho.write_bytes(b"video")
        assert not (pasta / "saida.mp4").exists()

    assert (pasta / "saida.mp4").read_bytes() == b"video"
    assert not grav.caminho.exists()
    assert _arquivos(pasta) == ["saida.mp4"]
    assert grav.artefato == ArtefatoGravado("saida.mp4", _sha(b"video"), 5)


def test_gravacao_atomica_substitui_destino_existente(armazem):
    armazem.gravar(USUARIO, VIDEO, "saida.mp4", b"antigo")

    with armazem.gravacao_atomica(USUARIO, VIDEO, "saida.mp4") as grav:
        grav.caminho.write_bytes(b"novo")

    assert armazem.ler(USUARIO, VIDEO, "saida.mp4") == b"novo"
    assert grav.artefato.sha256 == _sha(b"novo")


def test_gravacao_atomica_com_excecao_remove_temporario_e_preserva_destino(armazem, raiz):
    armazem.gravar(USUARIO, VIDEO, "saida.mp4", b"antigo")
    pasta = raiz / str(USUARIO) / str(VIDEO)

    with pytest.raises(RuntimeError, match="boom"):
        with armazem.gravacao_atomica(USUARIO, VIDEO, "saida.mp4") as grav:
            grav.caminho.write_bytes(b"parcial")
            raise RuntimeError("boom")

    assert not grav.caminho.exists()
    assert _arquivos(pasta) == ["saida.mp4"]
    assert armazem.ler(USUARIO, VIDEO, "saida.mp4") == b"antigo"


def test_gravacao_atomica_com_excecao_nao_cria_destino_novo(armazem, raiz):
    with pytest.raises(RuntimeError):
        with armazem.gravacao_atomica(USUARIO, VIDEO, "novo.mp4") as grav:
            grav.caminho.write_bytes(b"parcial")
            raise RuntimeError("falha")

    assert not armazem.existe(USUARIO, VIDEO, "novo.mp4")
    assert not grav.caminho.exists()


def test_gravacao_atomica_sem_temporario_falha_e_nao_cria_destino(armazem, raiz):
    with pytest.raises(ErroArmazenamento):
        with armazem.gravacao_atomica(USUARIO, VIDEO, "saida.mp4"):
            pass

    assert not armazem.existe(USUARIO, VIDEO, "saida.mp4")


def test_gravacao_atomica_sem_temporario_preserva_destino_anterior(armazem):
    armazem.gravar(USUARIO, VIDEO, "saida.mp4", b"antigo")

    with pytest.raises(ErroArmazenamento):
        with armazem.gravacao_atomica(USUARIO, VIDEO, "saida.mp4"):
            pass

    assert armazem.ler(USUARIO, VIDEO, "saida.mp4") == b"antigo"


@pytest.mark.parametrize("nome", ["../x", "a/../b", "/abs", ""])
def test_gravacao_atomica_valida_o_nome_antes_de_abrir(armazem, nome):
    with pytest.raises(CaminhoInvalido):
        with armazem.gravacao_atomica(USUARIO, VIDEO, nome):
            pytest.fail("não deveria entrar no bloco")


def test_falha_em_os_replace_nao_deixa_temporario_e_preserva_destino(armazem, raiz, monkeypatch):
    armazem.gravar(USUARIO, VIDEO, "a.json", b"antigo")
    pasta = raiz / str(USUARIO) / str(VIDEO)

    def falhar(*_args, **_kwargs):
        raise OSError("disco cheio simulado")

    monkeypatch.setattr(os, "replace", falhar)
    with pytest.raises((OSError, ErroArmazenamento)):
        armazem.gravar(USUARIO, VIDEO, "a.json", b"novo")
    monkeypatch.undo()

    assert _arquivos(pasta) == ["a.json"]
    assert armazem.ler(USUARIO, VIDEO, "a.json") == b"antigo"


def test_falha_em_os_replace_em_gravacao_atomica_limpa_temporario(armazem, raiz, monkeypatch):
    pasta = raiz / str(USUARIO) / str(VIDEO)

    def falhar(*_args, **_kwargs):
        raise OSError("falha simulada")

    monkeypatch.setattr(os, "replace", falhar)
    with pytest.raises((OSError, ErroArmazenamento)):
        with armazem.gravacao_atomica(USUARIO, VIDEO, "a.mp4") as grav:
            grav.caminho.write_bytes(b"dados")
    monkeypatch.undo()

    assert not grav.caminho.exists()
    assert not (pasta / "a.mp4").exists()
    assert _arquivos(pasta) == []


# concorrência


def test_gravacoes_concorrentes_nao_misturam_conteudo(armazem, raiz):
    conteudos = [bytes([65 + i]) * (200_000 + i) for i in range(8)]
    barreira = threading.Barrier(8)
    erros: list[BaseException] = []

    def gravar(dados: bytes) -> None:
        try:
            barreira.wait(timeout=10)
            armazem.gravar(USUARIO, VIDEO, "disputado.bin", dados)
        except BaseException as erro:
            erros.append(erro)

    threads = [threading.Thread(target=gravar, args=(c,)) for c in conteudos]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    # No Windows, substituições simultâneas podem recusar o acesso; nunca no POSIX.
    toleraveis = [e for e in erros if os.name == "nt" and isinstance(e, PermissionError)]
    assert erros == toleraveis
    assert len(erros) < len(conteudos)
    final = armazem.ler(USUARIO, VIDEO, "disputado.bin")
    assert final in conteudos
    assert _arquivos(raiz / str(USUARIO) / str(VIDEO)) == ["disputado.bin"]


def test_gravacoes_concorrentes_em_arquivos_distintos(armazem, raiz):
    erros: list[BaseException] = []

    def gravar(i: int) -> None:
        try:
            armazem.gravar(USUARIO, VIDEO, f"p{i}.json", str(i).encode())
        except BaseException as erro:
            erros.append(erro)

    threads = [threading.Thread(target=gravar, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert erros == []
    assert _arquivos(raiz / str(USUARIO) / str(VIDEO)) == sorted(f"p{i}.json" for i in range(8))
    assert all(armazem.ler(USUARIO, VIDEO, f"p{i}.json") == str(i).encode() for i in range(8))
