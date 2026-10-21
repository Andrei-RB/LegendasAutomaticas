# CLAUDE.md — LegendasAutomáticas v2

Guia de trabalho para o Claude Code. Leia inteiro antes de qualquer tarefa. Ele substitui o histórico de conversa.

## 1. O produto em uma frase

Estúdio **local (Docker)** que recebe um vídeo longo e entrega **cortes virais verificados** (9:16), **legendas com modelos virais** (MP4 + SRT para o CapCut) e **textos de postagem** (TikTok, Shorts, Reels, YouTube). Uso pessoal hoje; arquitetura pronta para virar SaaS. É peça de portfólio: qualidade de produto premiado em cada detalhe.

## 2. Estado atual (atualize esta seção ao fim de cada Sprint)

- **Fase:** planejamento concluído → **próxima tarefa: S0** (issue #2 e sub-issues #12–#18).
- **Código legado (v1)** em `app/` + `frontend/frontend_app.py` (Streamlit) + `launcher.py`. Ele será **migrado/removido na S0**. Não evolua o legado: só reaproveite o que o plano manda.
- **Fontes da verdade:**
  - Plano completo, com decisões D1–D40 e F1–F10: [`docs/plano-v2.md`](docs/plano-v2.md).
  - Sprints e tarefas: [`docs/sprints/`](docs/sprints/). Elas são espelhadas no GitHub (issues + milestones) pela Action `sincronizar-github`.
  - Em caso de conflito: **issue do GitHub > docs/sprints > plano-v2 > este arquivo**. Se encontrar divergência, avise e corrija a documentação.

## 3. Princípios inegociáveis

1. **A IA nunca inventa tempo.** Os tempos de corte e de legenda vêm de sinais medidos (Whisper, alinhamento, cenas, áudio). A IA só **escolhe IDs** (candidato, variante, frase, palavra), avalia e escreve texto.
2. **Toda saída de IA é validada:**
   - JSON schema estrito;
   - IDs existentes, sem repetição;
   - citações literais da transcrição;
   - correções com os mesmos índices.
   Se for inválida: 1 retry e depois o próximo provedor.
3. **Consenso:** um corte só é aprovado com 2 juízes de famílias diferentes + validadores de código.
4. **Tudo tem reserva.** Cota esgotada ou provedor fora do ar nunca quebra o pipeline.
5. **Gratuito sempre que possível:**
   - Qwen local para volume;
   - Gemini **só no nível gratuito**;
   - Claude pela assinatura, com teto diário.
6. **Prévia = vídeo final.** O mesmo pacote Remotion desenha a legenda no navegador e no render.
7. **Qualidade máxima de vídeo:** sempre a partir do original, num único encode final (x264 CRF 17).
8. **Segurança por padrão:**
   - nenhum segredo no código, em log ou em resposta;
   - todo dado filtrado por `user_id`;
   - `subprocess` sempre com lista de argumentos;
   - transcrição tratada como **dado não confiável** (prompt injection).

## 4. Arquitetura alvo

```
frontend (React+Vite) ─► api (FastAPI) ─► Redis/Celery ─► worker-gpu | worker-cpu | worker-ai | render (Remotion)
                              │                               │
                          PostgreSQL                     ollama (Qwen 3.5 9B / Gemma 4 E4B)
```

**Pipeline** (cada etapa idempotente via `execucoes_etapa` + `hash_entrada`):
1. `ingestao` → proxy, áudio, forma de onda.
2. `sinais`: asr, diarização, eventos de áudio, prosódia, cenas, rostos.
3. `linha_tempo` → `candidatos` (só código) → `triagem` (Qwen) → `juiz` (Gemini; Gemma de reserva) → `editor` (Claude) → `consenso`.
4. Revisão humana.
5. `enquadramento` → `legendas` (`DocumentoLegenda`) → `render` (camada de legenda com alfa + ffmpeg) → `postagens`.

**Roteador de IA** (`backend/app/ia/roteador.py`):

| Tarefa | Primário → reserva |
|---|---|
| triagem, correção e enriquecimento da legenda | Qwen → regras |
| juiz multimodal | Gemini → Gemma |
| editor-chefe e postagens | Claude (`claude -p`) → Haiku (API) → Qwen |
| hashtags em alta | Claude + WebSearch, com cache de 24 h |

## 5. Estrutura do repositório (alvo após a S0)

```
backend/app/{api/v1,nucleo,modelos,esquemas,pipeline/etapas,ia/{provedores,prompts},midia,workers}
backend/{alembic,testes,avaliacao}
frontend/                  React + Vite + TS (Tailwind, shadcn/ui, TanStack Query, Zustand, i18n)
pacotes/modelos-legenda/   Componentes Remotion + schema EspecModelo (compartilhado frontend ↔ render)
render/                    Serviço Node que renderiza a camada de legenda
recursos/{fontes,emoji}/   Fontes OFL e emojis Noto (com licenças)
infra/                     docker-compose.yml, Dockerfiles, .env.example
docs/                      plano-v2.md, sprints/
scripts/                   sincronizar_github.py
```

## 6. Convenções

- **Idioma:** tudo em **PT-BR**: código, identificadores (sem acento: `analise`, `corte`, `legenda`), comentários, commits, docs e interface. A tradução para inglês é feita pelo usuário no fim do projeto.
- **Documentação curta e simples.** Nada de textos longos. Prefira tabela e checklist.
- **Python:** 3.12, tipado, Pydantic v2, SQLAlchemy 2, `ruff` (lint e formatação). Funções puras sempre que possível (blocos, snap, validadores).
- **TypeScript:** `strict`, Zod nas fronteiras, tipos gerados do OpenAPI. Nunca redefinir à mão um tipo que vem da API.
- **Comentários:** só o "porquê" não óbvio. Siga o estilo do código ao redor.
- **Prompts:** em `backend/app/ia/prompts/<tarefa>/vN.md`. Mudou o prompt, sobe a versão; a versão entra no cache e nos julgamentos.
- **Commits:** imperativo em PT-BR (`feat: ...`, `fix: ...`, `docs: ...`), pequenos e com escopo de uma tarefa.

## 7. Como trabalhar numa tarefa

1. Ler a issue (objetivo, checklist, aceite) e a seção correspondente do `docs/plano-v2.md`.
2. Criar um branch `s<N>/<descricao-curta>` a partir da `main` (ou o branch indicado pela sessão).
3. Implementar o **mínimo que cumpre o aceite**. Não alargar o escopo; ideia nova vai para o backlog (`docs/sprints/sprint-9-backlog.md`).
4. Testes primeiro onde houver regra: validadores, alinhamento, blocos, roteador (provedores mockados).
5. Rodar as verificações (seção 8). Tudo verde antes de fazer commit.
6. PR com `Closes #N`, preenchendo o template. Marcar a checklist da issue.
7. Ao fim de uma Sprint: atualizar a seção 2 deste arquivo.

## 8. Comandos

> Os comandos abaixo valem **a partir da S0**. Até lá, o legado roda como descrito no `README.md`.

| Ação | Comando |
|---|---|
| Subir tudo | `docker compose -f infra/docker-compose.yml up -d` |
| GPU ok? | `docker compose -f infra/docker-compose.yml exec worker-gpu nvidia-smi` |
| Migrações | `docker compose ... exec api alembic upgrade head` |
| Lint backend | `ruff check backend && ruff format --check backend` |
| Testes backend | `pytest backend -m "not lento"` |
| Testes frontend | `cd frontend && npm run test` |
| E2E | `cd frontend && npx playwright test` |
| Avaliação | `make avaliar` (precision@N, WER, ablação) |
| Sincronizar GitHub | automático no push de `docs/sprints/**`; local: `GITHUB_TOKEN=... python scripts/sincronizar_github.py --repo Andrei-RB/LegendasAutomaticas` |

## 9. Limites do hardware (decidem o design)

RTX 4060 Ti **8 GB VRAM** · 16 GB RAM · Ryzen 7 5700X · Windows + Docker Desktop (WSL2).

- **Um modelo por vez na GPU:** lock `gpu:lock` no Redis (vale também para o Ollama, com `OLLAMA_KEEP_ALIVE=0`). Liberar VRAM depois de cada uso.
- `.wslconfig` com `memory=12GB`, `swap=8GB`. Volumes nomeados, nunca em `/mnt/c`.
- Vídeo de até 1 h. Meta: galeria pronta em 20–35 min.

## 10. IA externa: regras de uso

- **Claude** (`CLAUDE_MODE=subscription|api|off`):
  - `claude -p` com `--allowedTools WebSearch` apenas, num diretório vazio;
  - **no modo assinatura, `ANTHROPIC_API_KEY` não pode existir**, porque a cobrança iria para a API;
  - teto `CLAUDE_CHAMADAS_DIA`, com no máximo 1 editor e 1 postagem por análise;
  - para vender como serviço, usar o modo `api` (login claude.ai é proibido em produto para terceiros).
- **Gemini:**
  - só nível gratuito, com contador diário por modelo (reserva de 20%), e 429 vai para a reserva;
  - no nível gratuito, o Google pode usar os dados;
  - para SaaS, trocar de nível.
- **Nunca** enviar o vídeo inteiro para uma IA externa: apenas trechos do top 10 em 360p.

## 11. O que NÃO fazer

- Não pedir à IA números de tempo, nem aceitar tempo vindo dela.
- Não editar, sem pedido explícito, o legado (`app/`, Streamlit, `launcher.py`) além do que a S0 manda.
- Não adicionar dependência pesada sem justificar na PR (VRAM e RAM são escassas).
- Não commitar `.env`, modelos, vídeos, `dados/` ou saídas.
- Não pular os validadores "só para testar".
- Não criar documentação longa.

## 12. Definição de pronto (toda tarefa)

- [ ] Aceite da issue cumprido e demonstrável.
- [ ] Testes novos cobrindo a regra; `ruff` + `pytest` + `vitest` verdes.
- [ ] Sem segredo, sem vazamento de dado entre usuários, erros com mensagem amigável.
- [ ] Funciona com as IAs externas desligadas (reservas).
- [ ] Docs atualizadas **só se** o comportamento visível mudou (curto).
