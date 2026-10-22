<!-- epic: 🧱 S0 — Fundação | labels: epic, sprint-0 -->
**1. Objetivo:** criar o monorepo, subir todos os serviços com Docker e GPU, e entregar banco, login, executor de pipeline, frontend base e CI.

**2. Escopo:**

| Issue | Entrega |
|---|---|
| #12 | Monorepo e reaproveitamento do código da versão 1 |
| #13 | Docker Compose com GPU (Windows + WSL2) |
| #14 | PostgreSQL, Alembic e modelos base |
| #15 | Login JWT e escopo por usuário |
| #16 | Executor de pipeline idempotente e progresso via SSE |
| #17 | Frontend base (Vite + React + TypeScript) |
| #18 | CI (ruff, pytest, vitest, playwright) |

**3. Ordem e dependências:**

| Ordem | Issue | Depende de |
|---|---|---|
| 1 | #12 | — |
| 2 | #13 | #12 |
| 3 | #14 | #12, #13 |
| 4 | #15 | #14 |
| 5 | #16 | #13, #14, #15 |
| 5 | #17 | #13, #15 (pode ocorrer em paralelo à #16) |
| 6 | #18 | #12, #14, #17 |

**4. Pronto quando:**

| Verificação | Comando |
|---|---|
| Serviços saudáveis | `docker compose -f infra/docker-compose.yml up -d` e `docker compose -f infra/docker-compose.yml ps` sem serviço `unhealthy` |
| GPU no worker | `docker compose -f infra/docker-compose.yml exec worker-gpu nvidia-smi` |
| Migrações | `docker compose -f infra/docker-compose.yml exec api alembic upgrade head` |
| Testes | `ruff check backend && ruff format --check backend`, `pytest backend -m "not lento"`, `cd frontend && npm run test` |
| CI | Workflow verde na `main` e em PR |

**5. Riscos:**

| Risco | Mitigação |
|---|---|
| GPU indisponível no container | Validar o runtime NVIDIA e o driver antes da #13 (`docker info`, `nvidia-smi`) |
| RAM de 16 GB insuficiente para todos os serviços | `.wslconfig` (`memory=12GB`, `swap=8GB`); workers com limite de memória |
| Divergência entre modelos SQLAlchemy e migrações | `alembic check` no CI |
| Dependências do frontend sem justificativa | Stack fixada no plano (seção Frontend); acréscimos justificados no PR |

**Fora de escopo:** qualquer etapa real do pipeline (ingestão, ASR, sinais, IA). Começa na S1.

<!-- issue: [S0] Monorepo novo (backend/ frontend/ infra/ pacotes/ render/) | labels: infra, sprint-0 -->
**1. Objetivo:** reorganizar as pastas no mesmo repositório (o histórico é preservado), reaproveitando o que funciona da versão 1 e removendo o que sai.

**2. Contexto:**
- Decisões D22 e D23 de `docs/plano-v2.md`; seções "Estrutura do backend" e "Reaproveitado do código atual".
- Estrutura de destino: `CLAUDE.md`, seção 7.
- Código atual: `app/` (api, core, schemas, security, services, workers), `frontend/frontend_app.py`, `launcher.py`, `tests/test_api.py`.
- O branch `origin/Testes` (2 commits não mesclados) contém o endpoint `/health` com `lifespan`, o reforço de `middleware.py` e `validation.py` e a configuração de CORS por variável de ambiente. Reaproveitar esses trechos extraindo os arquivos (`git show origin/Testes:<caminho>`), sem mesclar o branch, porque ele conflita com a reorganização. O `Dockerfile` e o `docker-compose.yml` do branch pertencem à #13.

**3. Dependências:** nenhuma.

**4. Tarefas:**
- [ ] Criar `backend/app/{api/v1,nucleo,modelos,esquemas,pipeline,ia,midia,workers}` com `__init__.py`.
- [ ] Mover e adaptar para a nova estrutura:

| Origem (v1) | Destino |
|---|---|
| `app/api/endpoints.py` | `backend/app/api/v1/` |
| `app/core/config.py`, `app/core/logger.py` | `backend/app/nucleo/` |
| `app/security/validation.py`, `app/security/middleware.py` | `backend/app/nucleo/` (segurança) |
| `app/services/audio_service.py` | `backend/app/midia/` |
| `app/workers/celery_worker.py`, `app/workers/tasks.py` | `backend/app/workers/` |
| `app/schemas/job.py` | `backend/app/esquemas/` |
| `tests/test_api.py` | `backend/testes/` |

- [ ] Reaproveitar do branch `origin/Testes`: `/health` (com `lifespan`), reforço de `middleware.py` e `validation.py`, CORS por variável de ambiente.
- [ ] Remover `frontend/frontend_app.py`, `launcher.py`, `como-usar-commands.txt` e o `StaticFiles` montado em "/".
- [ ] Corrigir a mensagem "500 MB": o limite exibido vem da configuração.
- [ ] Corrigir `format_timestamp`: arredondar ao milissegundo em vez de truncar.
- [ ] Configurar `ruff` (`pyproject.toml`) e mover as dependências para `backend/`.
- [ ] Atualizar o `README.md` (estrutura e execução local) apenas no que mudou.

**5. Fora de escopo:** Docker e Compose (#13); banco (#14); login (#15); executor (#16); frontend (#17); CI (#18); alteração de comportamento dos endpoints além das duas correções acima.

**6. Testes exigidos:**
- Testes atuais adaptados em `backend/testes/` (o teste que espera `GET /` com 200 muda, pois o `StaticFiles` sai).
- `GET /health` retorna 200.
- `format_timestamp`: 1,9996 s resulta em `00:00:02,000`; 0 s resulta em `00:00:00,000`.
- Mensagem de limite de tamanho derivada da configuração (alterar o limite no teste e conferir o valor exibido).

**7. Aceite:**
- `ruff check backend && ruff format --check backend` sem erros.
- `pytest backend -m "not lento"` verde.
- `cd backend && uvicorn app.main:app` sobe e `curl -s http://127.0.0.1:8000/health` retorna 200.
- `git ls-files | grep -E "launcher.py|frontend_app.py|como-usar-commands.txt"` sem resultado.

<!-- issue: [S0] Docker Compose com GPU (Windows + WSL2) | labels: infra, sprint-0 -->
**1. Objetivo:** subir todo o sistema com um comando, com acesso à GPU nos serviços que a usam.

**2. Contexto:**
- Decisões D17, D18 e D21 de `docs/plano-v2.md`; seção "Arquitetura" (serviços e pontos críticos da infraestrutura).
- Restrições de hardware: `CLAUDE.md`, seção 11 (um modelo por vez na GPU; 16 GB de RAM).
- Base reaproveitável no branch `origin/Testes`: rede `legenda_net`, healthchecks, `depends_on` com `service_healthy`, limite de memória do worker, usuário não root no `Dockerfile`.
- Três correções obrigatórias ao reaproveitar: (1) a senha padrão do Redis no compose é removida e passa a ser obrigatória (`${SENHA_REDIS:?}`); (2) os bind mounts `./uploads`, `./outputs` e `./logs` são substituídos por volumes nomeados; (3) a imagem base passa de Python 3.11 para 3.12.
- O `.wslconfig` do host (`memory=12GB`, `swap=8GB`) é pré-requisito documentado no guia, não parte do compose.

**3. Dependências:** #12 (layout `backend/` e endpoint `/health`).

**4. Tarefas:**
- [ ] `infra/docker-compose.yml` com os serviços `api`, `worker-gpu`, `worker-cpu`, `worker-ai`, `beat`, `redis`, `postgres`, `ollama`, `render` e `frontend`. Serviços sem implementação ainda sobem com processo mínimo e healthcheck, substituído nas sprints correspondentes.
- [ ] GPU via `deploy.resources.reservations.devices` e `NVIDIA_DRIVER_CAPABILITIES=compute,video,utility` em `worker-gpu` e `ollama`.
- [ ] `worker-gpu`: imagem com CUDA e ffmpeg com NVENC; concorrência 1.
- [ ] `ollama`: `OLLAMA_KEEP_ALIVE=0` e `OLLAMA_MAX_LOADED_MODELS=1`.
- [ ] `worker-ai`: `CLAUDE_CONFIG_DIR` apontando para um volume nomeado dedicado, sem montar `~/.claude` do host; entrypoint que aborta se `ANTHROPIC_API_KEY` estiver definida com `CLAUDE_MODE=subscription`.
- [ ] Volumes nomeados para dados, banco, Redis e Ollama; nenhum caminho em `/mnt/c`.
- [ ] Portas publicadas apenas em `127.0.0.1`; contêineres sem root; `restart` e limites de memória por serviço.
- [ ] `infra/.env.example` com todos os segredos comentados: `POSTGRES_PASSWORD`, `SENHA_REDIS`, `JWT_SECRET`, `GEMINI_API_KEY`, `HF_TOKEN`, `CLAUDE_CODE_OAUTH_TOKEN`, `ANTHROPIC_API_KEY` (opcional), `CLAUDE_MODE`.
- [ ] Guia curto em `docs/guia-ambiente.md`: Docker Desktop, WSL2, driver NVIDIA, `.wslconfig`, verificação da GPU.

**5. Fora de escopo:** filas e executor (#16); instalação e uso do Claude CLI (S3); download de modelos do Ollama (S1/S3); proxy reverso, TLS e implantação em produção.

**6. Testes exigidos:**
- `docker compose -f infra/docker-compose.yml config -q` válido (executável no CI, sem GPU).
- Ausência de segredos padrão: `git grep -n "ChaveSegura" -- infra/` sem resultado.
- Subida sem `.env` falha com mensagem que nomeia a variável ausente.
- Verificações com GPU (`nvidia-smi`, NVENC) executadas localmente e registradas no PR, pois o CI não tem GPU.

**7. Aceite:**
- `docker compose -f infra/docker-compose.yml up -d` seguido de `docker compose -f infra/docker-compose.yml ps` sem serviço `unhealthy`.
- `docker compose -f infra/docker-compose.yml exec worker-gpu nvidia-smi` lista a GPU.
- `docker compose -f infra/docker-compose.yml exec worker-gpu ffmpeg -hide_banner -encoders` inclui `h264_nvenc`.
- `docker volume ls` lista os volumes nomeados e `git grep -n "/mnt/c" infra/` não retorna nada.

<!-- issue: [S0] PostgreSQL + Alembic + modelos base | labels: backend, sprint-0 -->
**1. Objetivo:** criar o banco com as tabelas do plano, versionado por migrações.

**2. Contexto:**
- Decisões D3, D19 e D20 de `docs/plano-v2.md`; seção "Modelo de dados".
- Isolamento por usuário: `CLAUDE.md`, seção 5, item 8.
- `modelos_legenda` e `fontes` guardam registros de sistema e de usuário: `user_id` aceita nulo apenas nesses dois casos. `cache_hashtags` é compartilhado por nicho e plataforma e não tem `user_id`. Registrar essa decisão no PR.

**3. Dependências:** #12 (estrutura `nucleo/` e `modelos/`), #13 (serviço `postgres`).

**4. Tarefas:**
- [ ] SQLAlchemy 2 tipado (`Mapped`) em `backend/app/modelos/` e sessão em `backend/app/nucleo/banco.py`, configurada por `DATABASE_URL`.
- [ ] Alembic em `backend/alembic/` com migração inicial.
- [ ] Tabelas: `usuarios`, `videos`, `analises`, `execucoes_etapa`, `candidatos`, `julgamentos`, `cortes`, `documentos_legenda`, `modelos_legenda`, `fontes`, `exportacoes`, `textos_postagem`, `cache_hashtags`, `hashtags_usuario`, `chamadas_ia`, `feedback`.
- [ ] Toda tabela de domínio com `user_id` (chave estrangeira) e índice.
- [ ] `execucoes_etapa`: restrição de unicidade em (`analise_id`, `etapa`, `hash_entrada`).
- [ ] `videos.expira_em` (7 dias) e `cortes.expira_em` (30 dias); datas em UTC; colunas JSONB para `documentos_legenda` e `modelos_legenda`.

**5. Fora de escopo:** regras de retenção (S7); consultas de negócio; dados iniciais dos 8 modelos de legenda (S5b).

**6. Testes exigidos:** executados contra PostgreSQL real (serviço do compose e do CI), sem SQLite.
- `alembic upgrade head` em base vazia e `alembic downgrade base` sem erro.
- `alembic check` sem diferenças entre modelos e migrações.
- Teste de metadados: toda tabela de domínio possui `user_id` indexado, exceto as listadas na seção 2.
- Violação da unicidade de `execucoes_etapa` rejeitada pelo banco.

**7. Aceite:**
- `docker compose -f infra/docker-compose.yml exec api alembic upgrade head` conclui numa base vazia.
- `docker compose -f infra/docker-compose.yml exec api alembic check` sem pendências.
- `pytest backend -m "not lento"` verde.

<!-- issue: [S0] Login JWT simples e escopo por usuário | labels: backend, sprint-0 -->
**1. Objetivo:** criar um login simples, pronto para multiusuário, com todo dado acessível apenas pelo dono.

**2. Contexto:**
- Decisão D3 de `docs/plano-v2.md`; `CLAUDE.md`, seção 5, item 8 (consultas filtradas por `user_id`, segredos fora do código e dos logs).
- O frontend usa o mesmo domínio da API por meio de proxy (#17), o que permite cookie `SameSite` restritivo.

**3. Dependências:** #14 (tabela `usuarios`).

**4. Tarefas:**
- [ ] Cadastro, login, logout e consulta do usuário atual em `backend/app/api/v1/auth.py`.
- [ ] Senha com argon2; JWT em cookie `httpOnly`, `SameSite` e `Secure` configurável; expiração configurável.
- [ ] `JWT_SECRET` obrigatório (mínimo de 32 bytes); a API não inicia sem ele; algoritmo fixo e verificado na validação.
- [ ] Cadastro permitido apenas enquanto não existir usuário ou quando `PERMITIR_CADASTRO=true`.
- [ ] Dependência `usuario_atual` em todas as rotas, exceto `/health`, cadastro e login.
- [ ] Toda consulta e todo acesso a arquivo filtrados por `user_id`; recurso de outro usuário responde 404.
- [ ] Mensagem de erro idêntica para e-mail inexistente e senha incorreta.
- [ ] Proteção contra CSRF nas rotas que alteram estado: verificação dos cabeçalhos `Origin`/`Sec-Fetch-Site` contra a origem permitida, além do cookie `SameSite`.
- [ ] Logout revoga o JWT: o `jti` entra em lista de revogação no Redis até a expiração do token.

**5. Fora de escopo:** limite de taxa e bloqueio por tentativas (S7); renovação de token; recuperação de senha; login social; assistente de primeiro uso (S7).

**6. Testes exigidos:**
- Usuário A não lê, altera nem remove recurso do usuário B (resposta 404).
- Token expirado, adulterado ou com algoritmo `none` resulta em 401.
- Rota protegida sem cookie resulta em 401.
- O banco guarda hash argon2; a senha em texto não aparece no banco nem nos logs.
- Cookie emitido com `httpOnly` e `SameSite`.
- POST de outra origem ou sem `Origin` permitido resulta em 403.
- Token usado após o logout resulta em 401.
- Cadastro bloqueado quando já existe usuário e `PERMITIR_CADASTRO` não está ativo.

**7. Aceite:** `pytest backend/testes -k isolamento` verde, com um teste que prova que o usuário A não acessa os dados do usuário B.

<!-- issue: [S0] Executor de pipeline idempotente + progresso via SSE | labels: backend, sprint-0 -->
**1. Objetivo:** criar a base de todas as etapas do processamento: execução idempotente, retomável e com progresso em tempo real.

**2. Contexto:**
- Seção "Pipeline" de `docs/plano-v2.md`; `CLAUDE.md`, seções 5 (princípios 1 e 2), 6 e 11 (`gpu:lock`).
- O Celery é apenas transporte; o estado fica no banco (`execucoes_etapa`).
- Armazenamento em disco: `dados/<user_id>/<video_id>/`, com identificadores (UUID) gerados pelo servidor; o nome original do upload nunca compõe o caminho.

**3. Dependências:** #13 (Redis e Postgres), #14 (`execucoes_etapa`), #15 (`usuario_atual` no SSE).

**4. Tarefas:**
- [ ] `backend/app/pipeline/executor.py`: `hash_entrada` (SHA-256 de etapa, versão da etapa, hashes dos artefatos de entrada e parâmetros canonizados); pula a etapa se o hash já foi concluído; grava artefatos com escrita atômica (arquivo temporário e `os.replace`); registra status em `execucoes_etapa`.
- [ ] Filas Celery `gpu`, `cpu`, `ai` e `render`, com roteamento por tarefa.
- [ ] Lock `gpu:lock` no Redis: aquisição atômica com TTL, liberação somente pelo dono, sempre liberado em `finally`.
- [ ] Erros amigáveis (código e mensagem) sem expor caminhos, SQL ou rastreio; detalhes técnicos apenas no log.
- [ ] `GET /api/v1/analises/{id}/eventos` (SSE via Redis pub/sub), autenticado e restrito ao dono da análise.
- [ ] Interface `Armazenamento` com `ArmazenamentoLocal`, com proteção contra path traversal.
- [ ] Etapa de exemplo com 3 passos, usada nos testes.

**5. Fora de escopo:** etapas reais do pipeline (S1 em diante); cancelamento de análise; retenção de arquivos (S7).

**6. Testes exigidos:**
- Mesma entrada não reexecuta a etapa; entrada diferente reexecuta.
- Falha no passo 2 e nova execução: refaz apenas o passo 2 e os seguintes.
- Falha durante a gravação não deixa arquivo parcial.
- `gpu:lock` liberado após exceção e expirado por TTL quando o processo morre.
- Resposta de erro sem caminho, SQL ou rastreio.
- SSE entrega eventos somente ao dono da análise.
- `ArmazenamentoLocal` rejeita `..`, caminhos absolutos e links simbólicos que saem da raiz.

**7. Aceite:** `pytest backend/testes/pipeline -m "not lento"` verde, incluindo o teste em que uma etapa de exemplo que falha é retomada sem refazer as anteriores (verificado em `execucoes_etapa`).

<!-- issue: [S0] Frontend base (Vite + React + TS) | labels: frontend, sprint-0 -->
**1. Objetivo:** montar o esqueleto da interface, servido em contêiner e integrado ao login.

**2. Contexto:**
- Decisões D1, D15 e F1 de `docs/plano-v2.md`; seção "Frontend" (stack e S0).
- Convenções: `CLAUDE.md`, seção 8 (TypeScript `strict`, Zod nas fronteiras, tipos gerados do OpenAPI).
- O contêiner `frontend` serve a SPA com nginx e encaminha `/api` para a API, de modo que cookie e API ficam no mesmo domínio.

**3. Dependências:** #13 (serviço `frontend` no compose), #15 (rotas de login).

**4. Tarefas:**
- [ ] Vite, React, TypeScript `strict`, Tailwind, shadcn/ui, React Router, TanStack Query, Zustand e react-i18next (PT-BR).
- [ ] Tema escuro (padrão) e claro, com preferência persistida.
- [ ] Layout com menu, rotas de exemplo e tela de login; rotas protegidas redirecionam para o login.
- [ ] Cliente da API com tipos gerados do OpenAPI (`openapi-typescript`); o OpenAPI é exportado pelo backend sem subir servidor.
- [ ] Validação com Zod nas respostas e nos formulários.
- [ ] Textos de interface somente no catálogo de i18n.
- [ ] Dockerfile multiestágio (build com Node, execução com nginx sem root) com cabeçalhos de segurança.
- [ ] Vitest com Testing Library e Playwright configurados.

**5. Fora de escopo:** telas de vídeo, análise, galeria e editor (S1 em diante); Remotion e `pacotes/modelos-legenda` (S1/S5b); assistente de primeiro uso (S7).

**6. Testes exigidos:**
- Vitest: guarda de rota, tratamento de 401 no cliente da API, validação Zod do login, persistência do tema.
- Playwright (smoke): login, navegação e logout contra a API em contêiner.

**7. Aceite:**
- `cd frontend && npm run test` e `npm run build` sem erros.
- Os tipos gerados não divergem do backend (`npm run gerar:api` sem diferenças no `git diff`).
- Com os serviços ativos, o login funciona em `http://127.0.0.1:<porta>` servido pelo contêiner `frontend`.

<!-- issue: [S0] CI (ruff, pytest, vitest, playwright) | labels: testes, infra, sprint-0 -->
**1. Objetivo:** rodar as verificações automaticamente em cada push e PR, e impedir a mesclagem de código que as quebre.

**2. Contexto:**
- `CLAUDE.md`, seções 10 e 14; workflow existente `verificar-autoria`.
- A `main` exige o check `verificar` e PR para mesclagem; os novos checks são acrescentados a essa regra após a primeira execução verde.
- O CI não tem GPU: testes que a exigem usam o marcador `lento` e rodam localmente.

**3. Dependências:** #12 (layout `backend/`), #14 (PostgreSQL nos testes), #17 (frontend).

**4. Tarefas:**
- [ ] `.github/workflows/ci.yml` com jobs separados e `permissions: contents: read`.
- [ ] Backend: `ruff check`, `ruff format --check` e `pytest -m "not lento"` com serviços PostgreSQL e Redis; `alembic check`.
- [ ] Scripts do repositório: `pytest scripts/testes`.
- [ ] Frontend: `npm ci`, verificação de tipos, `vitest` e `build`; conferência dos tipos gerados do OpenAPI.
- [ ] E2E: Playwright (smoke) contra API, PostgreSQL, Redis e frontend, usando um arquivo de composição para CI sem serviços de GPU.
- [ ] `docker compose config -q` para validar o compose.
- [ ] Cache de dependências (pip e npm) e cancelamento de execuções antigas no mesmo PR.
- [ ] Badge de status no `README.md`.
- [ ] Após a primeira execução verde, incluir os jobs na proteção da `main`.

**5. Fora de escopo:** implantação contínua; testes com GPU; relatório de cobertura mínima.

**6. Testes exigidos:** um PR de teste com falha intencional em cada job (ruff, pytest, vitest) deixa o check vermelho; o PR de teste é descartado sem mesclar.

**7. Aceite:**
- Workflow verde em PR e na `main` (`gh run list --workflow ci.yml --limit 3`).
- Badge do `README.md` exibe o status.
- A proteção da `main` exige os jobs do CI (`gh api repos/:owner/:repo/branches/main/protection`).
