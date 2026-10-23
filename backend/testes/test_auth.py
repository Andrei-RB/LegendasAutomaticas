import statistics
import threading
import time
import uuid

import jwt
import pytest
import redis
from sqlalchemy import text

from app.nucleo.config_auth import config_auth as settings
from testes.auxiliares_auth import (
    BASE_AUTH,
    adulterar_carga,
    cabecalho_cookie,
    cadastrar,
    cookie_sessao,
    decodificar,
    entrar,
    montar_token,
    token_da_resposta,
    token_do_cliente,
    trocar_assinatura,
)
from testes.conftest import ORIGEM_PERMITIDA, SENHA_PADRAO

ORIGEM_ESTRANHA = "https://evil.example"


def _contar_usuarios(ambiente) -> int:
    with ambiente.motor.connect() as con:
        return con.execute(text("SELECT count(*) FROM usuarios")).scalar_one()


# --- cadastro -------------------------------------------------------------------------------


def test_cadastro_primeiro_usuario_retorna_201_sem_cookie(ambiente, novo_cliente):
    resposta = cadastrar(novo_cliente(), "ana@exemplo.com", SENHA_PADRAO)

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert set(corpo) == {"id", "email", "nome_usuario", "idioma"}
    uuid.UUID(corpo["id"])
    assert corpo["email"] == "ana@exemplo.com"
    assert corpo["idioma"] == "pt-BR"
    assert "set-cookie" not in resposta.headers
    assert SENHA_PADRAO not in resposta.text


def test_cadastro_normaliza_email_em_minusculas(ambiente, novo_cliente):
    resposta = cadastrar(novo_cliente(), "Ana.Silva@Exemplo.COM", SENHA_PADRAO)

    assert resposta.status_code == 201
    assert resposta.json()["email"] == "ana.silva@exemplo.com"
    with ambiente.motor.connect() as con:
        assert con.execute(text("SELECT email FROM usuarios")).scalars().all() == [
            "ana.silva@exemplo.com"
        ]


def test_cadastro_email_duplicado_retorna_409(ambiente, criar_usuario, novo_cliente, monkeypatch):
    criar_usuario("ana@exemplo.com", "ana")
    monkeypatch.setattr(settings, "PERMITIR_CADASTRO", True)

    resposta = cadastrar(novo_cliente(), "ana@exemplo.com", SENHA_PADRAO, "outra")

    assert resposta.status_code == 409
    assert _contar_usuarios(ambiente) == 1


def test_cadastro_email_com_caixa_diferente_conta_como_duplicado(
    ambiente, criar_usuario, novo_cliente, monkeypatch
):
    criar_usuario("ana@exemplo.com", "ana")
    monkeypatch.setattr(settings, "PERMITIR_CADASTRO", True)

    resposta = cadastrar(novo_cliente(), "ANA@Exemplo.COM", SENHA_PADRAO, "outra")

    assert resposta.status_code == 409
    assert _contar_usuarios(ambiente) == 1


def test_cadastro_nome_usuario_duplicado_retorna_409(
    ambiente, criar_usuario, novo_cliente, monkeypatch
):
    criar_usuario("ana@exemplo.com", "ana")
    monkeypatch.setattr(settings, "PERMITIR_CADASTRO", True)

    resposta = cadastrar(novo_cliente(), "outra@exemplo.com", SENHA_PADRAO, "ana")

    assert resposta.status_code == 409


def test_cadastro_bloqueado_com_usuario_existente_e_flag_desativada(
    ambiente, criar_usuario, novo_cliente
):
    criar_usuario("ana@exemplo.com", "ana")
    assert settings.PERMITIR_CADASTRO is False

    resposta = cadastrar(novo_cliente(), "bia@exemplo.com", SENHA_PADRAO, "bia")

    assert resposta.status_code == 403
    assert _contar_usuarios(ambiente) == 1


def test_cadastro_permitido_com_usuario_existente_e_flag_ativa(
    ambiente, criar_usuario, novo_cliente, monkeypatch
):
    criar_usuario("ana@exemplo.com", "ana")
    monkeypatch.setattr(settings, "PERMITIR_CADASTRO", True)

    resposta = cadastrar(novo_cliente(), "bia@exemplo.com", SENHA_PADRAO, "bia")

    assert resposta.status_code == 201
    assert _contar_usuarios(ambiente) == 2


def test_cadastro_concorrente_com_banco_vazio_cria_apenas_um(ambiente, novo_cliente):
    for rodada in range(5):
        with ambiente.motor.begin() as con:
            con.execute(text("TRUNCATE usuarios CASCADE"))
        clientes = [novo_cliente(), novo_cliente()]
        barreira = threading.Barrier(2)
        codigos: list[int] = []

        def tarefa(cliente_http, indice, barreira=barreira, codigos=codigos, rodada=rodada):
            barreira.wait(timeout=10)
            resposta = cadastrar(
                cliente_http, f"u{indice}_{rodada}@exemplo.com", SENHA_PADRAO, f"u{indice}_{rodada}"
            )
            codigos.append(resposta.status_code)

        threads = [threading.Thread(target=tarefa, args=(c, i)) for i, c in enumerate(clientes)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert sorted(codigos) == [201, 403], f"rodada {rodada}: {codigos}"
        assert _contar_usuarios(ambiente) == 1


def test_cadastro_rejeita_campos_extras_com_422(ambiente, novo_cliente):
    resposta = cadastrar(novo_cliente(), "ana@exemplo.com", SENHA_PADRAO, ativo=False, admin=True)

    assert resposta.status_code == 422
    assert _contar_usuarios(ambiente) == 0


@pytest.mark.parametrize(
    ("email", "senha"),
    [
        ("ana@exemplo.com", "curta123"),
        ("ana@exemplo.com", "123456789012"),
        ("ana@exemplo.com", "x" * 129),
        ("nao-e-email", SENHA_PADRAO),
        ("", SENHA_PADRAO),
        ("ana@", SENHA_PADRAO),
    ],
)
def test_cadastro_entrada_invalida_retorna_422_sem_ecoar_senha(
    ambiente, novo_cliente, email, senha
):
    resposta = cadastrar(novo_cliente(), email, senha)

    assert resposta.status_code == 422
    assert senha not in resposta.text
    assert _contar_usuarios(ambiente) == 0


def test_cadastro_sem_campo_obrigatorio_retorna_422(ambiente, novo_cliente):
    resposta = novo_cliente().post(
        f"{BASE_AUTH}/cadastro", json={"email": "ana@exemplo.com", "senha": SENHA_PADRAO}
    )

    assert resposta.status_code == 422


# --- login e cookie -------------------------------------------------------------------------


def test_login_valido_retorna_200_com_cookie_de_sessao(ambiente, criar_usuario, novo_cliente):
    usuario = criar_usuario()

    resposta = entrar(novo_cliente(), usuario.email, usuario.senha)

    assert resposta.status_code == 200
    token = token_da_resposta(resposta)
    assert token
    assert token not in resposta.text
    assert usuario.senha not in resposta.text


def test_login_aceita_email_com_caixa_diferente(ambiente, criar_usuario, novo_cliente):
    usuario = criar_usuario("ana@exemplo.com")

    assert entrar(novo_cliente(), "ANA@Exemplo.com", usuario.senha).status_code == 200


def test_cookie_tem_httponly_samesite_strict_path_e_max_age(ambiente, criar_usuario, novo_cliente):
    usuario = criar_usuario()

    morsel = cookie_sessao(entrar(novo_cliente(), usuario.email, usuario.senha))

    assert morsel["httponly"]
    assert morsel["samesite"].lower() == "strict"
    assert morsel["path"] == "/"
    assert int(morsel["max-age"]) == settings.JWT_EXPIRA_MINUTOS * 60


def test_cookie_max_age_acompanha_expiracao_configurada(
    ambiente, criar_usuario, novo_cliente, monkeypatch
):
    usuario = criar_usuario()
    monkeypatch.setattr(settings, "JWT_EXPIRA_MINUTOS", 5)

    resposta = entrar(novo_cliente(), usuario.email, usuario.senha)

    assert int(cookie_sessao(resposta)["max-age"]) == 300
    carga = decodificar(token_da_resposta(resposta))
    assert carga["exp"] - carga["iat"] == 300


@pytest.mark.parametrize("seguro", [True, False])
def test_cookie_secure_segue_a_configuracao(
    ambiente, criar_usuario, novo_cliente, monkeypatch, seguro
):
    usuario = criar_usuario()
    monkeypatch.setattr(settings, "COOKIE_SECURE", seguro)

    morsel = cookie_sessao(entrar(novo_cliente(), usuario.email, usuario.senha))

    assert bool(morsel["secure"]) is seguro


def test_token_emitido_usa_hs256_e_traz_claims_obrigatorias(ambiente, criar_usuario):
    usuario = criar_usuario()

    token = token_do_cliente(usuario.cliente)
    assert jwt.get_unverified_header(token)["alg"] == "HS256"
    carga = decodificar(token)
    assert carga["sub"] == usuario.id
    assert {"exp", "iat", "jti"} <= set(carga)
    assert carga["exp"] > time.time()


def test_cada_login_emite_jti_distinto(ambiente, criar_usuario, novo_cliente):
    usuario = criar_usuario()

    outro = entrar(novo_cliente(), usuario.email, usuario.senha)

    assert (
        decodificar(token_da_resposta(outro))["jti"]
        != decodificar(token_do_cliente(usuario.cliente))["jti"]
    )


def test_login_falha_tem_corpo_identico_para_email_inexistente_e_senha_errada(
    ambiente, criar_usuario, novo_cliente
):
    usuario = criar_usuario()

    inexistente = entrar(novo_cliente(), "ninguem@exemplo.com", "qualquer-senha-123")
    errada = entrar(novo_cliente(), usuario.email, "senha-errada-123456")

    assert inexistente.status_code == errada.status_code == 401
    assert inexistente.json() == errada.json()
    assert "set-cookie" not in inexistente.headers
    assert "set-cookie" not in errada.headers


def test_login_de_usuario_inativo_retorna_o_mesmo_401(ambiente, criar_usuario, novo_cliente):
    usuario = criar_usuario()
    errada = entrar(novo_cliente(), usuario.email, "senha-errada-123456")
    with ambiente.motor.begin() as con:
        con.execute(text("UPDATE usuarios SET ativo = false"))

    inativo = entrar(novo_cliente(), usuario.email, usuario.senha)

    assert inativo.status_code == 401
    assert inativo.json() == errada.json()
    assert "set-cookie" not in inativo.headers


def test_login_sem_campos_retorna_422(ambiente, novo_cliente):
    assert novo_cliente().post(f"{BASE_AUTH}/login", json={}).status_code == 422


def test_login_tempo_similar_para_email_inexistente_e_senha_errada(
    ambiente, criar_usuario, novo_cliente
):
    usuario = criar_usuario()
    cliente_http = novo_cliente()
    entrar(cliente_http, usuario.email, "aquecimento-123456")

    def medir(email: str) -> float:
        tempos = []
        for _ in range(5):
            inicio = time.perf_counter()
            entrar(cliente_http, email, "senha-errada-123456")
            tempos.append(time.perf_counter() - inicio)
        return statistics.median(tempos)

    existente = medir(usuario.email)
    inexistente = medir("ninguem@exemplo.com")

    assert inexistente >= 0.5 * existente


# --- /eu e rotas protegidas ----------------------------------------------------------------


def test_eu_retorna_dados_do_usuario_logado(ambiente, usuario_logado):
    resposta = usuario_logado.cliente.get(f"{BASE_AUTH}/eu")

    assert resposta.status_code == 200
    assert resposta.json() == {
        "id": usuario_logado.id,
        "email": usuario_logado.email,
        "nome_usuario": usuario_logado.nome_usuario,
        "idioma": "pt-BR",
    }
    assert "senha" not in resposta.text


@pytest.mark.parametrize(
    ("metodo", "caminho"),
    [
        ("get", f"{BASE_AUTH}/eu"),
        ("post", "/api/v1/upload-video"),
        ("get", f"/api/v1/status/{uuid.uuid4()}"),
        ("get", f"/api/v1/download/{uuid.uuid4()}"),
    ],
)
def test_rota_protegida_sem_cookie_retorna_401(ambiente, novo_cliente, metodo, caminho):
    kwargs = {"files": {"file": ("v.mp4", b"x", "video/mp4")}} if metodo == "post" else {}

    resposta = getattr(novo_cliente(), metodo)(caminho, **kwargs)

    assert resposta.status_code == 401


def test_health_nao_exige_autenticacao(ambiente, novo_cliente):
    assert novo_cliente().get("/health").status_code == 200


def test_token_valido_montado_pelo_teste_e_aceito(ambiente, usuario_logado, novo_cliente):
    token = montar_token(usuario_logado.id)

    resposta = novo_cliente().get(f"{BASE_AUTH}/eu", headers=cabecalho_cookie(token))

    assert resposta.status_code == 200


def _expirado(u):
    return montar_token(u.id, expira_em=-60)


def _alg_none(u):
    return montar_token(u.id, algoritmo="none")


def _hs512(u):
    return montar_token(u.id, algoritmo="HS512")


def _hs384(u):
    return montar_token(u.id, algoritmo="HS384")


def _sem_exp(u):
    return montar_token(u.id, omitir=("exp",))


def _sem_jti(u):
    return montar_token(u.id, omitir=("jti",))


def _sem_iat(u):
    return montar_token(u.id, omitir=("iat",))


def _sem_sub(u):
    return montar_token(u.id, omitir=("sub",))


def _sub_inexistente(_u):
    return montar_token(uuid.uuid4())


def _sub_invalido(_u):
    return montar_token("nao-e-um-uuid")


def _segredo_errado(u):
    return montar_token(u.id, chave="outro-segredo-com-bem-mais-de-trinta-e-dois-bytes")


def _assinatura_trocada(u):
    return trocar_assinatura(montar_token(u.id))


def _carga_adulterada(u):
    return adulterar_carga(montar_token(u.id), exp=int(time.time()) + 10**7)


def _carga_com_outro_usuario(u):
    return adulterar_carga(montar_token(u.id), sub=str(uuid.uuid4()))


def _lixo(_u):
    return "isto.nao.e-jwt"


def _vazio(_u):
    return ""


CASOS_TOKEN_INVALIDO = [
    _expirado,
    _alg_none,
    _hs512,
    _hs384,
    _sem_exp,
    _sem_jti,
    _sem_iat,
    _sem_sub,
    _sub_inexistente,
    _sub_invalido,
    _segredo_errado,
    _assinatura_trocada,
    _carga_adulterada,
    _carga_com_outro_usuario,
    _lixo,
    _vazio,
]


@pytest.mark.parametrize("construir", CASOS_TOKEN_INVALIDO, ids=lambda f: f.__name__.strip("_"))
def test_token_invalido_retorna_401(ambiente, usuario_logado, novo_cliente, construir):
    token = construir(usuario_logado)

    resposta = novo_cliente().get(f"{BASE_AUTH}/eu", headers=cabecalho_cookie(token))

    assert resposta.status_code == 401


def test_token_invalido_tambem_nega_rota_de_negocio(ambiente, usuario_logado, novo_cliente):
    cabecalho = cabecalho_cookie(montar_token(usuario_logado.id, algoritmo="none"))

    resposta = novo_cliente().get(f"/api/v1/status/{uuid.uuid4()}", headers=cabecalho)

    assert resposta.status_code == 401


def test_usuario_desativado_depois_do_login_perde_acesso(ambiente, usuario_logado):
    assert usuario_logado.cliente.get(f"{BASE_AUTH}/eu").status_code == 200
    with ambiente.motor.begin() as con:
        con.execute(
            text("UPDATE usuarios SET ativo = false WHERE id = :i"), {"i": usuario_logado.id}
        )

    assert usuario_logado.cliente.get(f"{BASE_AUTH}/eu").status_code == 401


def test_usuario_removido_depois_do_login_perde_acesso(ambiente, usuario_logado):
    with ambiente.motor.begin() as con:
        con.execute(text("DELETE FROM usuarios WHERE id = :i"), {"i": usuario_logado.id})

    assert usuario_logado.cliente.get(f"{BASE_AUTH}/eu").status_code == 401


def test_isolamento_cada_cookie_enxerga_somente_o_proprio_usuario(ambiente, criar_usuario):
    a = criar_usuario("a@exemplo.com", "usuario_a")
    b = criar_usuario("b@exemplo.com", "usuario_b")

    assert a.cliente.get(f"{BASE_AUTH}/eu").json()["id"] == a.id
    assert b.cliente.get(f"{BASE_AUTH}/eu").json()["id"] == b.id
    assert a.id != b.id


# --- logout e revogação --------------------------------------------------------------------


def test_logout_retorna_204_e_limpa_o_cookie(ambiente, usuario_logado):
    resposta = usuario_logado.cliente.post(f"{BASE_AUTH}/logout")

    assert resposta.status_code == 204
    morsel = cookie_sessao(resposta)
    assert morsel.value == ""
    assert morsel["max-age"] == "0"
    assert morsel["path"] == "/"


def test_token_usado_depois_do_logout_retorna_401(ambiente, usuario_logado, novo_cliente):
    token = token_do_cliente(usuario_logado.cliente)
    assert novo_cliente().get(f"{BASE_AUTH}/eu", headers=cabecalho_cookie(token)).status_code == 200

    usuario_logado.cliente.post(f"{BASE_AUTH}/logout")

    reutilizado = novo_cliente().get(f"{BASE_AUTH}/eu", headers=cabecalho_cookie(token))
    assert reutilizado.status_code == 401


def test_logout_grava_jti_no_redis_com_ttl_limitado_pela_expiracao(ambiente, usuario_logado):
    carga = decodificar(token_do_cliente(usuario_logado.cliente))

    usuario_logado.cliente.post(f"{BASE_AUTH}/logout")

    chave = f"revogado:{carga['jti']}"
    assert ambiente.redis.exists(chave) == 1
    ttl = ambiente.redis.ttl(chave)
    assert 0 < ttl <= carga["exp"] - time.time() + 1


def test_logout_nao_afeta_token_de_outro_usuario(ambiente, criar_usuario):
    a = criar_usuario("a@exemplo.com", "usuario_a")
    b = criar_usuario("b@exemplo.com", "usuario_b")

    a.cliente.post(f"{BASE_AUTH}/logout")

    assert a.cliente.get(f"{BASE_AUTH}/eu").status_code == 401
    assert b.cliente.get(f"{BASE_AUTH}/eu").status_code == 200


def test_logout_nao_afeta_outra_sessao_do_mesmo_usuario(ambiente, criar_usuario, novo_cliente):
    usuario = criar_usuario()
    segunda = novo_cliente()
    assert entrar(segunda, usuario.email, usuario.senha).status_code == 200

    usuario.cliente.post(f"{BASE_AUTH}/logout")

    assert segunda.get(f"{BASE_AUTH}/eu").status_code == 200


def test_logout_sem_cookie_e_idempotente_204_sem_efeito(ambiente, novo_cliente):
    resposta = novo_cliente().post(f"{BASE_AUTH}/logout")

    assert resposta.status_code == 204
    assert ambiente.redis.keys("revogado:*") == []


def test_logout_com_token_forjado_nao_grava_revogacao(ambiente, usuario_logado, novo_cliente):
    forjado = trocar_assinatura(montar_token(usuario_logado.id))

    resposta = novo_cliente().post(f"{BASE_AUTH}/logout", headers=cabecalho_cookie(forjado))

    assert resposta.status_code in (204, 401)
    assert ambiente.redis.keys("revogado:*") == []


def test_redis_indisponivel_nega_acesso_a_rota_protegida(ambiente, usuario_logado, novo_cliente):
    from app.nucleo.dependencias import obter_redis

    token = token_do_cliente(usuario_logado.cliente)
    quebrado = redis.Redis(host="127.0.0.1", port=1, socket_connect_timeout=1, socket_timeout=1)
    ambiente.app.dependency_overrides[obter_redis] = lambda: quebrado

    resposta = novo_cliente().get(f"{BASE_AUTH}/eu", headers=cabecalho_cookie(token))

    assert resposta.status_code == 401


# --- senha e logs --------------------------------------------------------------------------


def test_banco_guarda_hash_argon2id_e_nao_a_senha(ambiente, novo_cliente):
    senha = f"Unica-{uuid.uuid4().hex}"
    cadastrar(novo_cliente(), "ana@exemplo.com", senha)

    with ambiente.motor.connect() as con:
        hashes = con.execute(text("SELECT senha_hash FROM usuarios")).scalars().all()
        linhas = con.execute(text("SELECT row_to_json(u)::text FROM usuarios u")).scalars().all()

    assert len(hashes) == 1
    assert hashes[0].startswith("$argon2id$")
    assert senha not in hashes[0]
    assert all(senha not in linha for linha in linhas)


def test_mesma_senha_gera_hashes_diferentes_entre_usuarios(ambiente, criar_usuario):
    criar_usuario("a@exemplo.com", "usuario_a", SENHA_PADRAO)
    criar_usuario("b@exemplo.com", "usuario_b", SENHA_PADRAO)

    with ambiente.motor.connect() as con:
        hashes = con.execute(text("SELECT senha_hash FROM usuarios")).scalars().all()

    assert len(hashes) == 2
    assert hashes[0] != hashes[1]


def test_senha_e_token_nao_aparecem_nos_logs_nem_nas_respostas(ambiente, novo_cliente, texto_logs):
    senha = f"Unica-{uuid.uuid4().hex}"
    errada = f"Errada-{uuid.uuid4().hex}"
    cliente_http = novo_cliente()
    respostas = [
        cadastrar(cliente_http, "ana@exemplo.com", senha),
        cadastrar(cliente_http, "invalido", senha),
        entrar(cliente_http, "ana@exemplo.com", errada),
        entrar(cliente_http, "ana@exemplo.com", senha),
    ]
    token = token_da_resposta(respostas[-1])
    respostas.append(cliente_http.get(f"{BASE_AUTH}/eu"))
    respostas.append(cliente_http.post(f"{BASE_AUTH}/logout"))

    logs = texto_logs()
    for segredo_texto in (senha, errada, token):
        assert segredo_texto not in logs
        assert all(segredo_texto not in r.text for r in respostas)
    assert "$argon2" not in logs
    assert all("$argon2" not in r.text for r in respostas)


# --- CSRF ----------------------------------------------------------------------------------

ROTAS_ESCRITA = [
    (
        "post",
        f"{BASE_AUTH}/login",
        {"json": {"email": "x@exemplo.com", "senha": "senha-qualquer-1"}},
    ),
    ("post", f"{BASE_AUTH}/logout", {}),
    (
        "post",
        f"{BASE_AUTH}/cadastro",
        {"json": {"email": "x@exemplo.com", "senha": SENHA_PADRAO, "nome_usuario": "x"}},
    ),
    ("post", "/api/v1/upload-video", {"files": {"file": ("v.mp4", b"x", "video/mp4")}}),
]
IDS_ROTAS = ["login", "logout", "cadastro", "upload"]


@pytest.mark.parametrize(("metodo", "caminho", "kwargs"), ROTAS_ESCRITA, ids=IDS_ROTAS)
@pytest.mark.parametrize(
    "origem",
    [
        ORIGEM_ESTRANHA,
        "null",
        "http://localhost:9999",
        "http://localhost:8501.evil.example",
        "http://evil.example/http://localhost:8501",
    ],
)
def test_csrf_origem_nao_permitida_retorna_403(
    ambiente, novo_cliente, metodo, caminho, kwargs, origem
):
    resposta = getattr(novo_cliente(origem=origem), metodo)(caminho, **kwargs)

    assert resposta.status_code == 403
    assert _contar_usuarios(ambiente) == 0


@pytest.mark.parametrize(("metodo", "caminho", "kwargs"), ROTAS_ESCRITA, ids=IDS_ROTAS)
def test_csrf_sem_origin_e_sem_sec_fetch_site_retorna_403(
    ambiente, novo_cliente, metodo, caminho, kwargs
):
    resposta = getattr(novo_cliente(origem=None), metodo)(caminho, **kwargs)

    assert resposta.status_code == 403


@pytest.mark.parametrize(("metodo", "caminho", "kwargs"), ROTAS_ESCRITA, ids=IDS_ROTAS)
def test_csrf_origin_permitido_passa(ambiente, novo_cliente, metodo, caminho, kwargs):
    resposta = getattr(novo_cliente(origem=ORIGEM_PERMITIDA), metodo)(caminho, **kwargs)

    assert resposta.status_code != 403


@pytest.mark.parametrize(("metodo", "caminho", "kwargs"), ROTAS_ESCRITA, ids=IDS_ROTAS)
def test_csrf_sec_fetch_site_same_origin_sem_origin_passa(
    ambiente, novo_cliente, metodo, caminho, kwargs
):
    cliente_http = novo_cliente(origem=None, **{"Sec-Fetch-Site": "same-origin"})

    assert getattr(cliente_http, metodo)(caminho, **kwargs).status_code != 403


@pytest.mark.parametrize("valor", ["cross-site", "same-site", "none", ""])
def test_csrf_sec_fetch_site_diferente_de_same_origin_retorna_403(ambiente, novo_cliente, valor):
    cliente_http = novo_cliente(origem=None, **{"Sec-Fetch-Site": valor})

    resposta = cliente_http.post(
        f"{BASE_AUTH}/login", json={"email": "x@exemplo.com", "senha": "s"}
    )

    assert resposta.status_code == 403


def test_csrf_origin_estranho_prevalece_sobre_sec_fetch_site_same_origin(ambiente, novo_cliente):
    cliente_http = novo_cliente(origem=ORIGEM_ESTRANHA, **{"Sec-Fetch-Site": "same-origin"})

    resposta = cliente_http.post(f"{BASE_AUTH}/logout")

    assert resposta.status_code == 403


@pytest.mark.parametrize("metodo", ["put", "patch", "delete"])
def test_csrf_cobre_put_patch_e_delete(ambiente, novo_cliente, metodo):
    cliente_http = novo_cliente(origem=ORIGEM_ESTRANHA)

    assert getattr(cliente_http, metodo)("/api/v1/upload-video").status_code == 403


def test_csrf_origem_estranha_nao_cria_sessao_nem_revoga_token(
    ambiente, usuario_logado, novo_cliente
):
    token = token_do_cliente(usuario_logado.cliente)
    atacante = novo_cliente(origem=ORIGEM_ESTRANHA)

    resposta = atacante.post(f"{BASE_AUTH}/logout", headers=cabecalho_cookie(token))

    assert resposta.status_code == 403
    assert ambiente.redis.keys("revogado:*") == []
    assert usuario_logado.cliente.get(f"{BASE_AUTH}/eu").status_code == 200


def test_csrf_nao_afeta_get(ambiente, usuario_logado, novo_cliente):
    token = token_do_cliente(usuario_logado.cliente)
    cliente_http = novo_cliente(origem=ORIGEM_ESTRANHA)

    assert cliente_http.get("/health").status_code == 200
    resposta = cliente_http.get(f"{BASE_AUTH}/eu", headers=cabecalho_cookie(token))
    assert resposta.status_code == 200
