# Sprints

Roadmap v2. O plano completo está em [`../plano-v2.md`](../plano-v2.md).

| Arquivo | Sprint |
|---|---|
| [00-roadmap.md](00-roadmap.md) | Visão geral |
| [sprint-0.md](sprint-0.md) | S0 Fundação |
| [sprint-1.md](sprint-1.md) | S1 Fatia vertical |
| [sprint-2.md](sprint-2.md) | S2 Sinais e perfis |
| [sprint-3.md](sprint-3.md) | S3 Roteador de IA e juízes |
| [sprint-4.md](sprint-4.md) | S4 Câmera virtual |
| [sprint-5a.md](sprint-5a.md) | S5a Legendas: precisão |
| [sprint-5b.md](sprint-5b.md) | S5b Legendas: modelos |
| [sprint-6.md](sprint-6.md) | S6 Postagens e re-gerar |
| [sprint-7.md](sprint-7.md) | S7 Endurecimento |
| [sprint-9-backlog.md](sprint-9-backlog.md) | Backlog |

## GitHub (issues, milestones e labels)

A Action `.github/workflows/sincronizar-github.yml` lê estes arquivos e sincroniza o GitHub sozinha a cada push que altera `docs/sprints/`. Ela pode ser rodada várias vezes sem duplicar nada.

- Cada épico vira um **milestone**, e suas tarefas entram nele.
- Rodar manualmente: aba **Actions → Sincronizar GitHub com as Sprints → Run workflow**.
- Rodar localmente: `GITHUB_TOKEN=... python scripts/sincronizar_github.py --repo Andrei-RB/LegendasAutomaticas` (use `--dry-run` para conferir antes).

Marcadores nos arquivos: `<!-- epic: Título | labels: ... -->` e `<!-- issue: Título | labels: ... -->`. Não mude o título de uma issue que já existe, porque a sincronização encontra as issues pelo título.
