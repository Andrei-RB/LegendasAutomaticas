<!-- epic: 🧱 S0 — Fundação | labels: epic, sprint-0 -->
**Objetivo:** criar o monorepo, subir tudo com Docker e GPU, montar banco, login e CI.

**Pronto quando:** `docker compose up` sobe todos os serviços, `nvidia-smi` funciona no `worker-gpu` e os testes passam no CI.

<!-- issue: [S0] Monorepo novo (backend/ frontend/ infra/ pacotes/ render/) | labels: infra, sprint-0 -->
**Objetivo:** reorganizar o repositório, reaproveitando o que funciona.

- [ ] Criar `backend/app/{api/v1,nucleo,modelos,esquemas,pipeline,ia,midia,workers}`.
- [ ] Mover e adaptar `security/validation.py`, `middleware.py`, `logger.py`, `audio_service.py` e a configuração do Celery.
- [ ] Remover Streamlit, `launcher.py`, `como-usar-commands.txt` e o `StaticFiles` em "/".
- [ ] Corrigir a mensagem "500 MB" (o limite real vem da config).
- [ ] Corrigir `format_timestamp` (arredondar, não truncar).

**Aceite:** a API sobe e os testes antigos, adaptados, passam.

<!-- issue: [S0] Docker Compose com GPU (Windows + WSL2) | labels: infra, sprint-0 -->
**Objetivo:** subir todo o sistema com um comando.

- [ ] Serviços: `api`, `worker-gpu`, `worker-cpu`, `worker-ai`, `beat`, `redis`, `postgres`, `ollama`, `render`, `frontend`.
- [ ] GPU via `deploy.resources.reservations.devices` + `NVIDIA_DRIVER_CAPABILITIES=compute,video,utility`.
- [ ] ffmpeg com NVENC no `worker-gpu`.
- [ ] Volumes nomeados (nunca em `/mnt/c`).
- [ ] `.env.example` com todos os segredos comentados.
- [ ] Guia curto: Docker Desktop, WSL2, driver NVIDIA, `.wslconfig` (`memory=12GB`, `swap=8GB`).

**Aceite:** `docker compose exec worker-gpu nvidia-smi` e `ffmpeg -encoders | grep nvenc` funcionam.

<!-- issue: [S0] PostgreSQL + Alembic + modelos base | labels: backend, sprint-0 -->
**Objetivo:** criar o banco com as tabelas do plano.

- [ ] SQLAlchemy + Alembic.
- [ ] Tabelas: `usuarios`, `videos`, `analises`, `execucoes_etapa`, `candidatos`, `julgamentos`, `cortes`, `documentos_legenda`, `modelos_legenda`, `fontes`, `exportacoes`, `textos_postagem`, `cache_hashtags`, `hashtags_usuario`, `chamadas_ia`, `feedback`.
- [ ] Toda tabela de domínio com `user_id` e índice.

**Aceite:** `alembic upgrade head` roda numa base vazia.

<!-- issue: [S0] Login JWT simples e escopo por usuário | labels: backend, sprint-0 -->
**Objetivo:** criar um login simples, já pronto para multiusuário.

- [ ] Cadastro e login (senha com argon2), JWT em cookie httpOnly.
- [ ] Dependência `usuario_atual` em todas as rotas.
- [ ] Toda consulta filtrada por `user_id`.

**Aceite:** um teste prova que o usuário A não acessa os dados do usuário B.

<!-- issue: [S0] Executor de pipeline idempotente + progresso via SSE | labels: backend, sprint-0 -->
**Objetivo:** criar a base de todas as etapas do processamento.

- [ ] `pipeline/executor.py`: calcula o `hash_entrada`, pula a etapa se já foi feita, grava com escrita atômica e registra em `execucoes_etapa`.
- [ ] Filas Celery `gpu`, `cpu`, `ai` e `render`, com lock `gpu:lock` no Redis.
- [ ] Erros amigáveis (código + mensagem), sem vazar detalhes internos.
- [ ] `GET /analises/:id/eventos` (SSE via Redis pub/sub).
- [ ] Interface `Armazenamento` com `ArmazenamentoLocal`.

**Aceite:** uma etapa de exemplo que falha pode ser retomada sem refazer as anteriores.

<!-- issue: [S0] Frontend base (Vite + React + TS) | labels: frontend, sprint-0 -->
**Objetivo:** montar o esqueleto da interface.

- [ ] Vite, Tailwind, shadcn/ui, React Router, TanStack Query, Zustand e react-i18next (PT-BR).
- [ ] Tema escuro (padrão) e claro.
- [ ] Layout com menu e tela de login.
- [ ] Cliente da API com tipos gerados do OpenAPI (`openapi-typescript`).

**Aceite:** login funciona contra a API, no container `frontend`.

<!-- issue: [S0] CI (ruff, pytest, vitest, playwright) | labels: testes, infra, sprint-0 -->
**Objetivo:** rodar os testes automaticamente em cada push.

- [ ] GitHub Actions: `ruff`, `pytest -m "not lento"`, `vitest` e Playwright (smoke).
- [ ] Badge no README.

**Aceite:** CI verde no push e no PR.
