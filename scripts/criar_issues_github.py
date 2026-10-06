#!/usr/bin/env python3
"""
Cria no GitHub as issues do roadmap a partir dos arquivos em docs/sprints/.

Estrutura criada:
    Roadmap (1 issue)
      └── Épico de cada Sprint (sub-issue do Roadmap)
            └── Tarefas da Sprint (sub-issues do Épico)

Requisitos:
    - GitHub CLI instalado (https://cli.github.com) e autenticado: `gh auth login`

Uso:
    python scripts/criar_issues_github.py --dry-run     # só mostra o que seria criado
    python scripts/criar_issues_github.py               # cria no repositório atual
    python scripts/criar_issues_github.py --repo Andrei-RB/LegendasAutomaticas

É seguro rodar mais de uma vez: issues com o mesmo título já existentes são reaproveitadas.
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SPRINTS_DIR = Path(__file__).resolve().parent.parent / "docs" / "sprints"

# <!-- tipo: Título | labels: a, b -->
MARKER = re.compile(r"^<!--\s*(roadmap|epic|issue):\s*(.+?)\s*\|\s*labels:\s*(.*?)\s*-->\s*$", re.MULTILINE)

LABEL_COLORS = {
    "roadmap": "5319e7",
    "epic": "3e4b9e",
    "bug": "d73a4a",
    "enhancement": "a2eeef",
    "ia": "8b5cf6",
    "legendas": "fbca04",
    "editor": "0e8a16",
    "audio": "1d76db",
    "frontend": "c5def5",
    "infra": "bfd4f2",
    "testes": "d4c5f9",
    "docs": "0075ca",
}


def parse_file(path: Path):
    """Divide um arquivo em blocos [(tipo, título, labels, corpo)]."""
    text = path.read_text(encoding="utf-8")
    matches = list(MARKER.finditer(text))
    blocks = []
    for idx, m in enumerate(matches):
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body = text[m.end():end].strip()
        labels = [label.strip() for label in m.group(3).split(",") if label.strip()]
        blocks.append((m.group(1), m.group(2), labels, body))
    return blocks


def gh(*args, capture=True):
    result = subprocess.run(["gh", *args], capture_output=capture, text=True, encoding="utf-8")
    if result.returncode != 0:
        print(f"\n❌ Falha em: gh {' '.join(args[:3])} ...\n{result.stderr}", file=sys.stderr)
        sys.exit(1)
    return result.stdout.strip() if capture else ""


def ensure_labels(repo: str, labels: set[str]):
    for label in sorted(labels):
        color = LABEL_COLORS.get(label, "ededed")
        if label.startswith("sprint-"):
            color = "f9d0c4"
        gh("label", "create", label, "--repo", repo, "--color", color, "--force")
    print(f"🏷️  {len(labels)} labels garantidas.")


def existing_issues(repo: str) -> dict[str, int]:
    out = gh("issue", "list", "--repo", repo, "--state", "all", "--limit", "1000", "--json", "number,title")
    return {item["title"]: item["number"] for item in json.loads(out or "[]")}


def create_issue(repo: str, title: str, labels: list[str], body: str, existing: dict[str, int]) -> int:
    if title in existing:
        print(f"↩️  Já existe #{existing[title]}: {title}")
        return existing[title]
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tmp:
        tmp.write(body)
        body_path = tmp.name
    args = ["issue", "create", "--repo", repo, "--title", title, "--body-file", body_path]
    for label in labels:
        args += ["--label", label]
    url = gh(*args)
    Path(body_path).unlink(missing_ok=True)
    number = int(url.rstrip("/").split("/")[-1])
    existing[title] = number
    print(f"✅ Criada #{number}: {title}")
    return number


def link_sub_issue(repo: str, parent: int, child: int):
    child_id = gh("api", f"repos/{repo}/issues/{child}", "--jq", ".id")
    result = subprocess.run(
        ["gh", "api", "-X", "POST", f"repos/{repo}/issues/{parent}/sub_issues", "-F", f"sub_issue_id={child_id}"],
        capture_output=True, text=True, encoding="utf-8",
    )
    # 422 = já é sub-issue (rodando o script de novo); não é erro.
    if result.returncode != 0 and "422" not in result.stderr and "already" not in result.stderr.lower():
        print(f"⚠️  Não foi possível ligar #{child} em #{parent}: {result.stderr.strip()}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", help="owner/repo (padrão: repositório da pasta atual)")
    parser.add_argument("--dry-run", action="store_true", help="só lista o que seria criado")
    args = parser.parse_args()

    files = sorted(SPRINTS_DIR.glob("*.md"))
    plan = [block for f in files for block in parse_file(f)]
    if not plan or plan[0][0] != "roadmap":
        sys.exit("O primeiro bloco precisa ser o roadmap (docs/sprints/00-roadmap.md).")

    if args.dry_run:
        for kind, title, labels, body in plan:
            indent = {"roadmap": "", "epic": "  └─ ", "issue": "       └─ "}[kind]
            print(f"{indent}{title}  [{', '.join(labels)}]  ({len(body)} caracteres)")
        epics = sum(1 for b in plan if b[0] == "epic")
        tasks = sum(1 for b in plan if b[0] == "issue")
        print(f"\nTotal: 1 roadmap, {epics} épicos, {tasks} tarefas.")
        return

    repo = args.repo or gh("repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner")
    print(f"📦 Repositório: {repo}\n")

    ensure_labels(repo, {label for _, _, labels, _ in plan for label in labels})
    existing = existing_issues(repo)

    roadmap = epic = None
    for kind, title, labels, body in plan:
        number = create_issue(repo, title, labels, body, existing)
        if kind == "roadmap":
            roadmap = number
        elif kind == "epic":
            epic = number
            link_sub_issue(repo, roadmap, number)
        else:
            link_sub_issue(repo, epic, number)

    print(f"\n🎉 Pronto! Veja em https://github.com/{repo}/issues/{roadmap}")


if __name__ == "__main__":
    main()
