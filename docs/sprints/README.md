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

## Criar as issues no GitHub

```bash
gh auth login
python scripts/criar_issues_github.py --dry-run   # confere
python scripts/criar_issues_github.py             # cria Roadmap → Épicos → Tarefas
```

Cria 74 issues (1 roadmap, 10 épicos e 63 tarefas). Pode rodar de novo sem duplicar.
