#!/usr/bin/env python3
"""Sincroniza issues, labels e milestones do GitHub com docs/sprints/ (idempotente).
Uso: GITHUB_TOKEN=... python scripts/sincronizar_github.py [--repo dono/repositorio] [--dry-run]"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

PASTA_SPRINTS = Path(__file__).resolve().parent.parent / "docs" / "sprints"
API = "https://api.github.com"

# <!-- tipo: Título | labels: a, b -->
MARCADOR = re.compile(r"^<!--\s*(roadmap|epic|issue):\s*(.+?)\s*\|\s*labels:\s*(.*?)\s*-->\s*$", re.MULTILINE)

CORES_LABELS = {
    "roadmap": "5319e7", "epic": "3e4b9e", "backlog": "cccccc",
    "backend": "1d76db", "frontend": "c5def5", "ia": "8b5cf6", "legendas": "fbca04",
    "cortes": "e99695", "render": "c2e0c6", "infra": "bfd4f2", "testes": "d4c5f9", "docs": "0075ca",
}


def ler_blocos():
    """Retorna [(tipo, titulo, labels, corpo, arquivo)] na ordem dos arquivos."""
    blocos = []
    for arquivo in sorted(PASTA_SPRINTS.glob("*.md")):
        texto = arquivo.read_text(encoding="utf-8")
        marcas = list(MARCADOR.finditer(texto))
        for i, m in enumerate(marcas):
            fim = marcas[i + 1].start() if i + 1 < len(marcas) else len(texto)
            labels = [x.strip() for x in m.group(3).split(",") if x.strip()]
            blocos.append((m.group(1), m.group(2), labels, texto[m.end():fim].strip(), arquivo.name))
    return blocos


def titulo_milestone(titulo_epico: str) -> str:
    """'🧱 S0 — Fundação' → 'S0 — Fundação'."""
    return re.sub(r"^[^\w\[]+", "", titulo_epico).strip()


class GitHub:
    def __init__(self, repo: str, token: str):
        self.repo, self.token = repo, token

    def chamar(self, metodo: str, caminho: str, dados=None):
        url = caminho if caminho.startswith("http") else f"{API}/repos/{self.repo}{caminho}"
        req = urllib.request.Request(url, method=metodo, data=json.dumps(dados).encode() if dados is not None else None)
        req.add_header("Authorization", f"Bearer {self.token}")
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        try:
            with urllib.request.urlopen(req) as resp:
                corpo = resp.read()
                return resp.status, (json.loads(corpo) if corpo else None), resp.headers
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}"), e.headers

    def listar(self, caminho: str):
        itens, url = [], f"{API}/repos/{self.repo}{caminho}{'&' if '?' in caminho else '?'}per_page=100"
        while url:
            status, dados, headers = self.chamar("GET", url)
            if status != 200:
                sys.exit(f"❌ GET {caminho} → {status}: {dados}")
            itens += dados
            proxima = re.search(r'<([^>]+)>;\s*rel="next"', headers.get("Link", "") or "")
            url = proxima.group(1) if proxima else None
        return itens


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    blocos = ler_blocos()
    if not blocos or blocos[0][0] != "roadmap":
        sys.exit("O primeiro bloco precisa ser o roadmap (docs/sprints/00-roadmap.md).")

    if args.dry_run:
        epico = None
        for tipo, titulo, labels, _, _ in blocos:
            if tipo == "epic":
                epico = titulo_milestone(titulo)
            ms = epico if tipo != "roadmap" else "-"
            print(f"{tipo:8} {titulo}  [{', '.join(labels)}]  milestone: {ms}")
        print(f"\nTotal: {len(blocos)} issues, {sum(b[0] == 'epic' for b in blocos)} milestones.")
        return

    token = os.environ.get("GITHUB_TOKEN")
    if not token or not args.repo:
        sys.exit("Defina GITHUB_TOKEN e --repo (ou GITHUB_REPOSITORY).")
    gh = GitHub(args.repo, token)

    # 1. Labels
    existentes = {l["name"] for l in gh.listar("/labels")}
    for label in sorted({l for b in blocos for l in b[2]} - existentes):
        cor = "f9d0c4" if label.startswith("sprint-") else CORES_LABELS.get(label, "ededed")
        gh.chamar("POST", "/labels", {"name": label, "color": cor})
        print(f"🏷️  label criada: {label}")

    # 2. Milestones
    milestones = {m["title"]: m["number"] for m in gh.listar("/milestones?state=all")}
    for tipo, titulo, _, corpo, _ in blocos:
        nome = titulo_milestone(titulo)
        if tipo == "epic" and nome not in milestones:
            descricao = corpo.splitlines()[0][:250] if corpo else ""
            status, dados, _ = gh.chamar("POST", "/milestones", {"title": nome, "description": descricao})
            if status != 201:
                sys.exit(f"❌ milestone {nome} → {status}: {dados}")
            milestones[nome] = dados["number"]
            print(f"🎯 milestone criado: {nome}")

    # 3 e 4. Issues
    issues = {i["title"]: i for i in gh.listar("/issues?state=all") if "pull_request" not in i}
    roadmap = epico = None
    milestone_atual = None
    for tipo, titulo, labels, corpo, _ in blocos:
        if tipo == "epic":
            milestone_atual = milestones[titulo_milestone(titulo)]
        ms = None if tipo == "roadmap" else milestone_atual
        issue = issues.get(titulo)
        if issue is None:
            dados_novos = {"title": titulo, "body": corpo, "labels": labels}
            if ms:
                dados_novos["milestone"] = ms
            status, issue, _ = gh.chamar("POST", "/issues", dados_novos)
            if status != 201:
                sys.exit(f"❌ issue {titulo} → {status}: {issue}")
            print(f"✅ criada #{issue['number']}: {titulo}")
            pai = roadmap if tipo == "epic" else epico if tipo == "issue" else None
            if pai:
                gh.chamar("POST", f"/issues/{pai}/sub_issues", {"sub_issue_id": issue["id"]})
        else:
            atuais = {l["name"] for l in issue.get("labels", [])}
            ms_atual = (issue.get("milestone") or {}).get("number")
            if not set(labels) <= atuais or ms_atual != ms:
                patch = {"labels": sorted(atuais | set(labels))}
                if ms:
                    patch["milestone"] = ms
                gh.chamar("PATCH", f"/issues/{issue['number']}", patch)
                print(f"🔄 atualizada #{issue['number']}: {titulo}")
        if tipo == "roadmap":
            roadmap = issue["number"]
        elif tipo == "epic":
            epico = issue["number"]

    print("\n🎉 GitHub sincronizado com docs/sprints/.")


if __name__ == "__main__":
    main()
