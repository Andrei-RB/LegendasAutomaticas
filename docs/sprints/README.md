# 📅 Sprints do projeto

O roadmap de melhorias está dividido em 8 Sprints. Cada uma tem um objetivo, uma definição de pronto e tarefas detalhadas (contexto, o que fazer, arquivos afetados, exemplo de código, critérios de aceite, como testar e dependências).

| Arquivo | Conteúdo |
|---|---|
| [00-roadmap.md](00-roadmap.md) | Visão geral, arquitetura alvo e convenções |
| [sprint-0.md](sprint-0.md) | 🧱 Fundação e correções |
| [sprint-1.md](sprint-1.md) | 🎯 Precisão da transcrição |
| [sprint-2.md](sprint-2.md) | 🤖 Integração com Gemini |
| [sprint-3.md](sprint-3.md) | 🎨 Modelos de legenda (.ass) e vídeo com legenda gravada |
| [sprint-4.md](sprint-4.md) | ✂️ Editor: cortes inteligentes |
| [sprint-5.md](sprint-5.md) | 🔊 Áudio e formato |
| [sprint-6.md](sprint-6.md) | 🚀 IA avançada |
| [sprint-7.md](sprint-7.md) | 🖥️ Interface e infraestrutura |

## Criar as issues no GitHub

Com o [GitHub CLI](https://cli.github.com) instalado e autenticado (`gh auth login`):

```bash
python scripts/criar_issues_github.py --dry-run   # confere o que será criado
python scripts/criar_issues_github.py             # cria Roadmap → Épicos → Tarefas (sub-issues)
```

O script cria as labels, as 55 issues e as liga como sub-issues. Ele pode ser rodado de novo sem duplicar nada.

Os comentários `<!-- epic: ... -->` e `<!-- issue: ... -->` nos arquivos marcam onde começa cada issue. Mantenha esse formato se for editar.
