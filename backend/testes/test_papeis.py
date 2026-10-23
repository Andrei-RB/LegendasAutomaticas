import importlib
import uuid
from collections.abc import Callable, Iterator

import psycopg.errors
import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError, ProgrammingError

from app.nucleo.config import settings

SENHA = "senha-de-teste-0123456789"
SENHA_NOVA = "outra-senha-de-teste-9876543210"
URL_INALCANCAVEL = "postgresql+psycopg://x:y@127.0.0.1:1/inexistente"
QTD_TABELAS = 16


def _papeis():
    return importlib.import_module("app.nucleo.papeis")


def _migrar():
    return importlib.import_module("app.nucleo.migrar")


def _consultar(url: str, sql: str, **params):
    motor = create_engine(url, isolation_level="AUTOCOMMIT")
    try:
        with motor.connect() as con:
            return con.execute(text(sql), params).all()
    finally:
        motor.dispose()


def _executar(url, sql: str) -> None:
    motor = create_engine(url, isolation_level="AUTOCOMMIT")
    try:
        with motor.connect() as con:
            con.execute(text(sql))
    finally:
        motor.dispose()


def _url_papel(url_dono: str, papel: str, senha: str):
    return make_url(url_dono).set(username=papel, password=senha)


def _tabelas(url: str) -> set[str]:
    motor = create_engine(url)
    try:
        return set(sa_inspect(motor).get_table_names())
    finally:
        motor.dispose()


def _papel_existe(url: str, papel: str) -> bool:
    return bool(_consultar(url, "SELECT 1 FROM pg_roles WHERE rolname = :p", p=papel))


def _remover_papel(url: str, papel: str) -> None:
    if _papel_existe(url, papel):
        _executar(url, f'DROP OWNED BY "{papel}"')
        _executar(url, f'DROP ROLE "{papel}"')


@pytest.fixture
def papel(banco_limpo: str) -> Iterator[str]:
    nome = f"viraliza_app_t_{uuid.uuid4().hex[:8]}"
    yield nome
    _remover_papel(banco_limpo, nome)


@pytest.fixture
def papel_padrao(banco_limpo: str) -> Iterator[str]:
    nome = "viraliza_app"
    if _papel_existe(banco_limpo, nome):
        pytest.fail(
            f"papel '{nome}' ja existe no cluster de teste: remova-o antes de executar.",
            pytrace=False,
        )
    yield nome
    _remover_papel(banco_limpo, nome)


@pytest.fixture
def aplicar(banco_migrado: str, papel: str) -> Callable[..., None]:
    def _aplicar(senha: str = SENHA) -> None:
        _papeis().aplicar_papel_app(banco_migrado, senha, papel=papel)

    return _aplicar


@pytest.fixture
def motor_papel(banco_migrado: str, papel: str, aplicar) -> Iterator[Callable[..., object]]:
    motores = []

    def _abrir(senha: str = SENHA):
        motor = create_engine(_url_papel(banco_migrado, papel, senha), isolation_level="AUTOCOMMIT")
        motores.append(motor)
        return motor

    aplicar()
    yield _abrir
    for motor in motores:
        motor.dispose()


def test_constante_papel_padrao():
    assert _papeis().PAPEL_APP == "viraliza_app"


def test_papel_criado_com_atributos_minimos(banco_migrado, papel, aplicar):
    aplicar()
    linha = _consultar(
        banco_migrado,
        "SELECT rolcanlogin, rolsuper, rolcreatedb, rolcreaterole, rolreplication, "
        "rolbypassrls FROM pg_roles WHERE rolname = :p",
        p=papel,
    )
    assert linha == [(True, False, False, False, False, False)]


def test_papel_executa_dml_em_usuarios_e_videos(motor_papel):
    motor = motor_papel()
    with motor.connect() as con:
        user_id = con.execute(
            text("INSERT INTO usuarios (nome_usuario) VALUES ('ana') RETURNING id")
        ).scalar()
        con.execute(
            text(
                "INSERT INTO videos (user_id, origem, caminho_original) "
                "VALUES (:u, 'arquivo', '/x.mp4')"
            ),
            {"u": user_id},
        )
        assert con.execute(text("SELECT count(*) FROM videos")).scalar() == 1
        assert (
            con.execute(
                text("UPDATE usuarios SET idioma = 'en' WHERE id = :u"), {"u": user_id}
            ).rowcount
            == 1
        )
        assert con.execute(text("SELECT idioma FROM usuarios")).all() == [("en",)]
        assert con.execute(text("DELETE FROM videos")).rowcount == 1
        assert con.execute(text("DELETE FROM usuarios")).rowcount == 1


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE TABLE intrusa (id int)",
        "DROP TABLE usuarios",
        "TRUNCATE usuarios",
        "ALTER TABLE usuarios ADD COLUMN x int",
        "CREATE ROLE intruso_t_papeis",
        "COPY (SELECT 1) TO PROGRAM 'true'",
        "SELECT * FROM alembic_version",
        "INSERT INTO alembic_version VALUES ('x')",
        "DELETE FROM alembic_version",
    ],
)
def test_papel_nao_executa_operacoes_privilegiadas(sql, motor_papel):
    motor = motor_papel()
    with motor.connect() as con, pytest.raises(ProgrammingError) as erro:
        con.execute(text(sql))
    assert isinstance(erro.value.orig, psycopg.errors.InsufficientPrivilege)


def test_banco_concede_connect_ao_papel_e_nao_a_public(banco_migrado, papel, aplicar):
    aplicar()
    assert _consultar(
        banco_migrado,
        "SELECT has_database_privilege(:p, current_database(), 'CONNECT')",
        p=papel,
    ) == [(True,)]
    assert _consultar(
        banco_migrado,
        "SELECT datacl IS NOT NULL FROM pg_database WHERE datname = current_database()",
    ) == [(True,)]
    assert _consultar(
        banco_migrado,
        "SELECT count(*) FROM pg_database d, aclexplode(d.datacl) a "
        "WHERE d.datname = current_database() AND a.grantee = 0",
    ) == [(0,)]


def test_papel_nao_tem_privilegios_sobre_alembic_version(banco_migrado, papel, aplicar):
    aplicar()
    privilegios = _consultar(
        banco_migrado,
        "SELECT p FROM unnest(ARRAY['SELECT','INSERT','UPDATE','DELETE','TRUNCATE',"
        "'REFERENCES','TRIGGER']) AS p "
        "WHERE has_table_privilege(:r, 'alembic_version', p)",
        r=papel,
    )
    assert privilegios == []


def test_papel_tem_dml_em_todas_as_tabelas_do_schema(banco_migrado, papel, aplicar):
    aplicar()
    faltantes = _consultar(
        banco_migrado,
        "SELECT t.tablename, p FROM pg_tables t, "
        "unnest(ARRAY['SELECT','INSERT','UPDATE','DELETE']) AS p "
        "WHERE t.schemaname = 'public' AND t.tablename <> 'alembic_version' "
        "AND NOT has_table_privilege(:r, format('public.%I', t.tablename), p)",
        r=papel,
    )
    assert faltantes == []
    assert len(_tabelas(banco_migrado) - {"alembic_version"}) == QTD_TABELAS


def test_papel_nao_recebe_privilegio_de_ddl_em_tabelas(banco_migrado, papel, aplicar):
    aplicar()
    indevidos = _consultar(
        banco_migrado,
        "SELECT t.tablename, p FROM pg_tables t, "
        "unnest(ARRAY['TRUNCATE','REFERENCES','TRIGGER']) AS p "
        "WHERE t.schemaname = 'public' AND has_table_privilege(:r, "
        "format('public.%I', t.tablename), p)",
        r=papel,
    )
    assert indevidos == []


def test_papel_acessa_tabela_criada_antes_de_ser_aplicado(banco_migrado, papel, aplicar):
    _executar(banco_migrado, "CREATE TABLE nova_tabela_t (id int)")
    aplicar()
    motor = create_engine(_url_papel(banco_migrado, papel, SENHA), isolation_level="AUTOCOMMIT")
    try:
        with motor.connect() as con:
            con.execute(text("INSERT INTO nova_tabela_t (id) VALUES (7)"))
            assert con.execute(text("SELECT id FROM nova_tabela_t")).all() == [(7,)]
            con.execute(text("UPDATE nova_tabela_t SET id = 8"))
            con.execute(text("DELETE FROM nova_tabela_t"))
    finally:
        motor.dispose()


def test_privilegios_padrao_valem_para_tabela_criada_apos_aplicar(banco_migrado, papel, aplicar):
    aplicar()
    _executar(banco_migrado, "CREATE TABLE nova_tabela_t (id int)")
    motor = create_engine(_url_papel(banco_migrado, papel, SENHA), isolation_level="AUTOCOMMIT")
    try:
        with motor.connect() as con:
            con.execute(text("INSERT INTO nova_tabela_t (id) VALUES (1)"))
            assert con.execute(text("SELECT count(*) FROM nova_tabela_t")).scalar() == 1
    finally:
        motor.dispose()


def test_aplicar_duas_vezes_nao_falha_e_mantem_alembic_version_fechada(
    banco_migrado, papel, aplicar
):
    aplicar()
    aplicar()
    assert _consultar(
        banco_migrado, "SELECT count(*) FROM pg_roles WHERE rolname = :p", p=papel
    ) == [(1,)]
    consulta = "SELECT has_table_privilege(:r, 'alembic_version', 'SELECT')"
    assert _consultar(banco_migrado, consulta, r=papel) == [(False,)]


def test_reaplicar_restaura_atributos_alterados(banco_migrado, papel, aplicar):
    aplicar()
    _executar(banco_migrado, f'ALTER ROLE "{papel}" CREATEDB CREATEROLE')
    aplicar()
    assert _consultar(
        banco_migrado,
        "SELECT rolcreatedb, rolcreaterole FROM pg_roles WHERE rolname = :p",
        p=papel,
    ) == [(False, False)]


def test_reaplicar_com_outra_senha_troca_a_senha(banco_migrado, papel, motor_papel, aplicar):
    aplicar(SENHA_NOVA)
    antigo = motor_papel(SENHA)
    with pytest.raises(OperationalError), antigo.connect():
        pass
    novo = motor_papel(SENHA_NOVA)
    with novo.connect() as con:
        assert con.execute(text("SELECT 1")).scalar() == 1


@pytest.mark.parametrize(
    "nome",
    [
        "Viraliza",
        "viraliza-app",
        "viraliza app",
        'viraliza"app',
        "viraliza;drop",
        "1viraliza",
        "viraliza.app",
        "",
        "a" * 64,
        "viraliza_ç",
    ],
)
def test_papel_invalido_levanta_valueerror_sem_executar_sql(nome):
    with pytest.raises(ValueError):
        _papeis().aplicar_papel_app(URL_INALCANCAVEL, SENHA, papel=nome)


@pytest.mark.parametrize("nome", ["Viraliza_T", "viraliza-t", "viraliza_t;x", "a" * 64])
def test_papel_invalido_nao_cria_papel(banco_limpo, nome):
    antes = _consultar(banco_limpo, "SELECT count(*) FROM pg_roles")
    with pytest.raises(ValueError):
        _papeis().aplicar_papel_app(banco_limpo, SENHA, papel=nome)
    assert _consultar(banco_limpo, "SELECT count(*) FROM pg_roles") == antes


@pytest.mark.parametrize("papel_valido", ["a", "_a", "a" * 63, "viraliza_app2"])
def test_papel_valido_passa_na_validacao(papel_valido):
    with pytest.raises(OperationalError):
        _papeis().aplicar_papel_app(URL_INALCANCAVEL, SENHA, papel=papel_valido)


@pytest.mark.parametrize("senha", ["", "curta", "Zq9#kL2$mP4&wR7"])
def test_senha_curta_levanta_valueerror_sem_vazar_a_senha(senha, banco_limpo, papel):
    with pytest.raises(ValueError) as erro:
        _papeis().aplicar_papel_app(banco_limpo, senha, papel=papel)
    if senha:
        assert senha not in str(erro.value)
    assert not _papel_existe(banco_limpo, papel)


def test_senha_com_16_caracteres_e_aceita(banco_migrado, papel):
    senha = "0123456789abcdef"
    assert len(senha) == 16
    _papeis().aplicar_papel_app(banco_migrado, senha, papel=papel)
    motor = create_engine(_url_papel(banco_migrado, papel, senha))
    try:
        with motor.connect() as con:
            assert con.execute(text("SELECT current_user")).scalar() == papel
    finally:
        motor.dispose()


@pytest.mark.parametrize(
    "senha",
    [
        "it's-a-pass-word-0123",
        "a;b;c;d;e;f;g;h;i;j;k",
        "x-- comentario ---- yy",
        "x'; DROP TABLE usuarios; --",
        'asp"as\\barra%s{0}$1$$',
        "senha-ção-ünï-çödé-123",
    ],
)
def test_senha_com_caracteres_perigosos_e_literal(banco_migrado, papel, senha):
    assert len(senha) >= 16
    _papeis().aplicar_papel_app(banco_migrado, senha, papel=papel)
    assert "usuarios" in _tabelas(banco_migrado)
    motor = create_engine(_url_papel(banco_migrado, papel, senha))
    try:
        with motor.connect() as con:
            assert con.execute(text("SELECT current_user")).scalar() == papel
    finally:
        motor.dispose()


def _preparar_migrar(monkeypatch, tmp_path, url: str, senha: str) -> None:
    _migrar()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(settings, "DATABASE_URL", SecretStr(url))
    monkeypatch.setattr(settings, "SENHA_PAPEL_APP", SecretStr(senha))


def test_migrar_cria_tabelas_e_papel_padrao(banco_limpo, papel_padrao, monkeypatch, tmp_path):
    senha = "a1" * 16
    _preparar_migrar(monkeypatch, tmp_path, banco_limpo, senha)
    _migrar().main()
    assert len(_tabelas(banco_limpo) - {"alembic_version"}) == QTD_TABELAS
    assert _papel_existe(banco_limpo, papel_padrao)
    motor = create_engine(
        _url_papel(banco_limpo, papel_padrao, senha), isolation_level="AUTOCOMMIT"
    )
    try:
        with motor.connect() as con:
            assert con.execute(text("SELECT count(*) FROM usuarios")).scalar() == 0
            with pytest.raises(ProgrammingError) as erro:
                con.execute(text("SELECT * FROM alembic_version"))
            assert isinstance(erro.value.orig, psycopg.errors.InsufficientPrivilege)
    finally:
        motor.dispose()


def test_migrar_segunda_execucao_e_idempotente(banco_limpo, papel_padrao, monkeypatch, tmp_path):
    _preparar_migrar(monkeypatch, tmp_path, banco_limpo, "a1" * 16)
    _migrar().main()
    _migrar().main()
    assert len(_tabelas(banco_limpo) - {"alembic_version"}) == QTD_TABELAS
    consulta = "SELECT has_table_privilege('viraliza_app', 'alembic_version', 'SELECT')"
    assert _consultar(banco_limpo, consulta) == [(False,)]
    assert _consultar(banco_limpo, "SELECT count(*) FROM alembic_version") == [(1,)]


def test_migrar_com_senha_vazia_levanta_valueerror_sem_tocar_no_banco(
    banco_limpo, papel_padrao, monkeypatch, tmp_path
):
    _preparar_migrar(monkeypatch, tmp_path, banco_limpo, "")
    with pytest.raises(ValueError):
        _migrar().main()
    assert _tabelas(banco_limpo) == set()
    assert not _papel_existe(banco_limpo, papel_padrao)


@pytest.mark.parametrize(
    "senha", ["m" * 32, "abc%40def" + "0" * 8, "senha com espaco 0123456789", "A" * 32]
)
def test_migrar_recusa_senha_nao_hexadecimal_sem_tocar_no_banco(
    senha, banco_limpo, papel_padrao, monkeypatch, tmp_path
):
    _preparar_migrar(monkeypatch, tmp_path, banco_limpo, senha)
    with pytest.raises(ValueError) as erro:
        _migrar().main()
    assert senha not in str(erro.value)
    assert _tabelas(banco_limpo) == set()
    assert not _papel_existe(banco_limpo, papel_padrao)


def test_senha_do_papel_e_armazenada_como_hash_scram(banco_migrado, papel, aplicar):
    aplicar()
    (armazenado,) = _consultar(
        banco_migrado, "SELECT rolpassword FROM pg_authid WHERE rolname = :p", p=papel
    )[0]
    assert armazenado.startswith("SCRAM-SHA-256$")
    assert SENHA not in armazenado


def test_gatilho_de_exportacao_funciona_com_o_papel_restrito(banco_migrado, papel, aplicar):
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import Session

    from app.modelos import Analise, Corte, Exportacao, ModeloLegenda, Usuario, Video
    from app.nucleo.banco import criar_motor

    aplicar()
    dono = criar_motor(banco_migrado)
    with Session(dono) as s:
        a, b = Usuario(nome_usuario="gat_a"), Usuario(nome_usuario="gat_b")
        s.add_all([a, b])
        s.flush()
        video = Video(user_id=a.id, origem="arquivo", caminho_original="/dados/v.mp4")
        s.add(video)
        s.flush()
        analise = Analise(user_id=a.id, video_id=video.id, parametros={})
        s.add(analise)
        s.flush()
        corte = Corte(user_id=a.id, analise_id=analise.id, inicio_s=0, fim_s=5)
        modelo_a = ModeloLegenda(user_id=a.id, nome="a", especificacao={})
        modelo_b = ModeloLegenda(user_id=b.id, nome="b", especificacao={})
        s.add_all([corte, modelo_a, modelo_b])
        s.commit()
        user_id, corte_id, id_a, id_b = a.id, corte.id, modelo_a.id, modelo_b.id
    dono.dispose()

    url = _url_papel(banco_migrado, papel, SENHA).render_as_string(hide_password=False)
    restrito = criar_motor(url)
    try:
        with Session(restrito) as s:
            s.add(Exportacao(user_id=user_id, corte_id=corte_id, modelo_legenda_id=id_b))
            with pytest.raises(IntegrityError) as erro:
                s.flush()
            assert erro.value.orig.diag.constraint_name == "ck_exportacoes_modelo_dono"
            s.rollback()
            s.add(Exportacao(user_id=user_id, corte_id=corte_id, modelo_legenda_id=id_a))
            s.commit()
    finally:
        restrito.dispose()
