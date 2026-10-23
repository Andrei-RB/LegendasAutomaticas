import importlib.util
from pathlib import Path

import pytest

CAMINHO = Path(__file__).resolve().parent.parent / "sincronizar_github.py"
spec = importlib.util.spec_from_file_location("sincronizar_github", CAMINHO)
sg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sg)

CORPO = "**1. Objetivo**\n\n- [ ] item a\n- [ ] item b\n\n**7. Aceite**\n\n`pytest`"


def issue(corpo, labels=("backend",), milestone=1):
    return {"body": corpo, "labels": [{"name": n} for n in labels], "milestone": {"number": milestone}}


def test_corpo_igual_nao_gera_patch():
    assert sg.montar_patch(issue(CORPO), ["backend"], 1, CORPO) == {}


def test_crlf_e_espacos_finais_sao_ignorados():
    assert sg.montar_patch(issue(CORPO.replace("\n", "\r\n") + "\r\n"), ["backend"], 1, CORPO) == {}


def test_checkbox_marcado_no_github_nao_gera_patch():
    marcado = CORPO.replace("- [ ] item a", "- [x] item a")
    assert sg.montar_patch(issue(marcado), ["backend"], 1, CORPO) == {}


def test_texto_diferente_gera_patch_de_corpo():
    patch = sg.montar_patch(issue(CORPO), ["backend"], 1, CORPO.replace("item b", "item c"))
    assert set(patch) == {"body"}
    assert "item c" in patch["body"]


def test_atualizacao_preserva_itens_marcados_e_a_estrutura():
    marcado = CORPO.replace("- [ ] item a", "- [x] item a")
    novo = CORPO.replace("item b", "item c")
    corpo = sg.montar_patch(issue(marcado), ["backend"], 1, novo)["body"]
    assert "- [x] item a" in corpo
    assert "- [ ] item c" in corpo
    assert corpo.count("\n") == novo.count("\n")


def test_item_com_texto_alterado_nao_herda_marcacao():
    marcado = CORPO.replace("- [ ] item a", "- [x] item a")
    novo = CORPO.replace("item a", "item a revisado")
    assert "- [ ] item a revisado" in sg.preservar_marcacoes(marcado, novo)


def test_labels_sao_somadas_sem_remover_as_existentes():
    patch = sg.montar_patch(issue(CORPO, labels=("backend", "manual")), ["backend", "infra"], 1, CORPO)
    assert patch == {"labels": ["backend", "infra", "manual"]}


def test_milestone_divergente_gera_patch_e_roadmap_sem_milestone_nao():
    assert sg.montar_patch(issue(CORPO, milestone=2), ["backend"], 1, CORPO) == {"milestone": 1}
    assert sg.montar_patch({"body": CORPO, "labels": [{"name": "roadmap"}]}, ["roadmap"], None, CORPO) == {}


def test_corpo_vazio_no_github_recebe_o_texto():
    assert "body" in sg.montar_patch({"body": None, "labels": []}, [], None, CORPO)


@pytest.mark.parametrize("titulo,esperado", [("🧱 S0 — Fundação", "S0 — Fundação"), ("[S0] Tarefa", "[S0] Tarefa")])
def test_titulo_milestone(titulo, esperado):
    assert sg.titulo_milestone(titulo) == esperado


def test_todos_os_arquivos_de_sprint_tem_blocos_validos():
    blocos = sg.ler_blocos()
    assert blocos[0][0] == "roadmap"
    titulos = [b[1] for b in blocos]
    assert len(titulos) == len(set(titulos)), "títulos duplicados quebram a busca por título"
    assert all(b[3] for b in blocos), "bloco sem corpo"


def test_issue_fechada_nao_tem_corpo_atualizado():
    fechada = {**issue(CORPO), "state": "closed"}
    assert sg.montar_patch(fechada, ["backend"], 1, CORPO.replace("item b", "item c")) == {}


def test_novo_com_crlf_equivale_ao_corpo_existente():
    assert sg.montar_patch(issue(CORPO), ["backend"], 1, CORPO.replace("\n", "\r\n")) == {}


def test_itens_duplicados_compartilham_a_marcacao():
    atual = "- [x] repetido\n- [ ] outro"
    novo = "- [ ] repetido\n- [ ] repetido\n- [ ] outro"
    assert sg.preservar_marcacoes(atual, novo) == "- [x] repetido\n- [x] repetido\n- [ ] outro"


def test_issue_de_outro_autor_nao_e_adotada():
    issues = [
        {"title": "A", "user": {"login": "dono"}},
        {"title": "B", "user": {"login": "intruso"}},
        {"title": "C", "user": {"login": "github-actions[bot]"}},
        {"title": "D", "user": {"login": "dono"}, "pull_request": {}},
    ]
    indice = sg.indexar_por_titulo(issues, "dono/repo")
    assert indice["A"] and indice["C"]
    assert indice["B"] is None
    assert "D" not in indice


def test_chamar_recusa_url_fora_da_api():
    with pytest.raises(SystemExit):
        sg.GitHub("dono/repo", "t").chamar("GET", "https://evil.example/x")


def test_chamar_devolve_texto_quando_o_erro_nao_e_json(monkeypatch):
    import io
    import urllib.error

    def falha(req):
        raise urllib.error.HTTPError(req.full_url, 502, "Bad Gateway", {}, io.BytesIO(b"<html>erro</html>"))

    monkeypatch.setattr(sg, "ABRIR", falha)
    status, dados, _ = sg.GitHub("dono/repo", "t").chamar("GET", "/issues")
    assert status == 502 and "erro" in dados


def test_redirecionamento_e_bloqueado():
    assert sg.SemRedirecionamento().redirect_request(None, None, 302, "", {}, "https://evil.example") is None


def test_issue_com_label_ui_recebe_o_bloco_de_frontend_uma_vez():
    bloco = sg.ARQUIVO_BLOCO_UI.read_text(encoding="utf-8").strip()
    com_ui = [b for b in sg.ler_blocos() if b[0] == "issue" and sg.LABEL_UI in b[2]]
    assert com_ui, "nenhuma issue de interface marcada com a label ui"
    assert all(b[3].count(bloco) == 1 for b in com_ui)


def test_issue_sem_label_ui_e_epicos_nao_recebem_o_bloco():
    bloco = sg.ARQUIVO_BLOCO_UI.read_text(encoding="utf-8").strip()
    outros = [b for b in sg.ler_blocos() if not (b[0] == "issue" and sg.LABEL_UI in b[2])]
    assert all(bloco not in b[3] for b in outros)


def test_todas_as_issues_de_tela_tem_a_label_ui():
    sem_ui = [b[1] for b in sg.ler_blocos() if b[0] == "issue" and "frontend" in b[2] and sg.LABEL_UI not in b[2]]
    sem_tela = {"[S0] Frontend base (Vite + React + TS)", "[Backlog] Limite de corpo no nginx para o upload de vídeo"}
    assert set(sem_ui) <= sem_tela, "issue de frontend com tela precisa da label ui"
