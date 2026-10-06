<!-- epic: 🖥️ Sprint 7 — Interface e infraestrutura | labels: epic, sprint-7, frontend, infra -->
## 🎯 Objetivo da Sprint

Deixar o app **gostoso de usar** e **fácil de instalar**:

- tela organizada com todas as opções, em passos;
- editor de legenda no navegador (corrigir uma palavra sem abrir o CapCut);
- histórico de vídeos processados;
- instalação com um comando (Docker), sem depender de WSL.

## ✅ Definição de pronto (DoD)

- [ ] Fluxo em passos: Enviar → Opções → Processar → Revisar/Editar → Exportar.
- [ ] Editar a legenda e exportar de novo sem reprocessar o vídeo.
- [ ] `docker compose up` sobe tudo em qualquer sistema.

## 📋 Tarefas

As tarefas estão listadas como sub-issues abaixo.

<!-- issue: [S7] Painel de opções em passos no frontend (wizard) | labels: enhancement, frontend, sprint-7 -->
## 🧩 Contexto

Com todas as Sprints, existem dezenas de opções. Jogar tudo numa tela assusta. Precisamos de **passos** e de **predefinições**.

## 🛠️ O que fazer

1. Reorganizar o `frontend_app.py` em módulos (`frontend/pages/`, `frontend/components/`, `frontend/api_client.py`).
2. Fluxo:
   1. **Enviar vídeo**;
   2. **Objetivo** (predefinições que preenchem as opções):
      - "Só legenda para o CapCut" → SRT, modo curto, sem render;
      - "Reels pronto" → cortes Normal + tema Hormozi + 9:16 + loudness + render;
      - "YouTube" → frases + capítulos + textos;
      - "Personalizado" → mostra todas as opções;
   3. **Opções avançadas** (expansíveis): legenda, IA, cortes, áudio, formato;
   4. **Processando**: progresso com a etapa atual;
   5. **Resultado**: prévia, editor, downloads, ações de IA extras.
3. Usar `st.session_state` para manter o estado entre passos e `st.query_params` para recuperar o job ao recarregar a página.
4. Opções de IA desabilitadas (com a explicação) quando o Gemini não estiver configurado (`/health`).
5. Lembrar as últimas opções usadas (arquivo local `~/.legendas/prefs.json` ou `localStorage`).

## ✅ Critérios de aceite

- [ ] Um usuário novo gera um "Reels pronto" em 3 cliques.
- [ ] Recarregar a página durante o processamento não perde o job.

## 🔗 Dependências

Sprint 0 (opções); recebe as opções das Sprints 1–6.

<!-- issue: [S7] Editor de legendas no navegador | labels: enhancement, frontend, legendas, sprint-7 -->
## 🧩 Contexto

Mesmo com IA, sempre sobra um erro ou outro. Hoje, para corrigir, é preciso editar no CapCut. Um editor simples no app resolve, e as correções servem para **todos** os formatos (SRT, ASS, vídeo, tradução).

## 🛠️ O que fazer

1. Endpoints:
   - `GET /api/v1/jobs/{job_id}/transcript` devolve os blocos/palavras;
   - `PATCH /api/v1/jobs/{job_id}/transcript` recebe as alterações (texto, emoji, destaque, ajuste fino de tempo), validadas com Pydantic: tempos dentro da duração, sem sobreposição, texto com tamanho máximo;
   - `POST /api/v1/jobs/{job_id}/export` gera de novo SRT/ASS/vídeo a partir do transcript editado.
2. Frontend:
   - tabela editável (`st.data_editor`) com: início, fim, texto, emoji, destaque;
   - destacar em amarelo as palavras de **baixa confiança** (Sprint 1) e as **alteradas pela IA** (Sprint 2), com o texto original na dica;
   - buscar e substituir ("capicute" → "CapCut" em todas as ocorrências);
   - player de vídeo ao lado: clicar numa linha pula para aquele tempo (`st.video(..., start_time=)`).
3. Salvar o histórico de versões (`transcript.v1.json`, `v2`...) para desfazer.
4. Opcional: "Adicionar ao vocabulário" a partir de uma correção, para os próximos vídeos.

## ✅ Critérios de aceite

- [ ] Corrigir uma palavra e exportar atualiza o SRT, o ASS e o vídeo (se pedido) sem transcrever de novo.
- [ ] Edições inválidas (tempo sobreposto) são recusadas com mensagem clara.

## 🔗 Dependências

Sprint 0 (transcript.json), Sprint 3 (exportação).

<!-- issue: [S7] Histórico de jobs com banco SQLite | labels: enhancement, infra, frontend, sprint-7 -->
## 🧩 Contexto

Hoje o estado do job vive só no Redis (expira) e não há como ver os vídeos processados antes.

## 🛠️ O que fazer

1. SQLite (`data/app.db`) com SQLAlchemy/SQLModel. Tabela `jobs`: `id`, `nome_original`, `criado_em`, `status`, `duracao`, `opcoes_json`, `arquivos_json`, `uso_ia_json`, `erro`.
2. Criar o registro no upload e atualizar nas mudanças de status (o worker atualiza no fim de cada etapa).
3. `GET /api/v1/jobs?limit=20` lista o histórico; `DELETE /api/v1/jobs/{id}` apaga o job e os arquivos dele.
4. Integrar com a limpeza automática (Sprint 0): ao apagar arquivos, marcar o job como `expirado`.
5. Frontend: aba "Histórico" com status, data, duração e botões (abrir, baixar, apagar).
6. Migrações simples (Alembic) para evoluir o schema sem perder dados.

## ✅ Critérios de aceite

- [ ] Reiniciar o app mantém o histórico.
- [ ] Apagar um job remove os arquivos do disco.

## 🔗 Dependências

Sprint 0.

<!-- issue: [S7] Docker Compose (API, worker, Redis, frontend) com suporte opcional a GPU | labels: infra, sprint-7 -->
## 🧩 Contexto

Hoje, para rodar, é preciso: Python + venv + WSL + Redis + FFmpeg no PATH + o launcher. Com Docker, qualquer computador roda com **um comando**.

## 🛠️ O que fazer

1. `Dockerfile` (base `python:3.11-slim` + `apt-get install ffmpeg fonts-noto-color-emoji`), usuário não-root.
2. `docker-compose.yml` com os serviços:
   - `redis` (imagem oficial `redis:7-alpine`);
   - `api` (uvicorn, porta 8000);
   - `worker` (celery, com o volume de modelos para não baixar de novo);
   - `beat` (limpeza agendada);
   - `frontend` (streamlit, porta 8501, `BACKEND_URL=http://api:8000/api/v1`).
3. Volumes: `uploads`, `outputs`, `models`, `data`, `logs`.
4. Perfil GPU: `docker-compose.gpu.yml` com `deploy.resources.reservations.devices` (NVIDIA Container Toolkit) e uma imagem base CUDA para o worker.
5. `.dockerignore` (venv, modelos, uploads, .env).
6. Healthchecks em todos os serviços (`/api/v1/health`, `redis-cli ping`).
7. README: seção "Rodando com Docker" (Windows com Docker Desktop, Linux, macOS).

## ✅ Critérios de aceite

- [ ] `docker compose up` numa máquina limpa sobe o app em `http://localhost:8501`.
- [ ] O worker com GPU funciona com `-f docker-compose.gpu.yml`.
- [ ] O CI faz o build da imagem (sem publicar).

## 🔗 Dependências

Sprint 0 (health, launcher).

<!-- issue: [S7] Segurança e robustez para uso fora do computador local | labels: infra, sprint-7 -->
## 🧩 Contexto

Se um dia o app for usado por outras pessoas ou ficar acessível na internet, algumas proteções passam a ser obrigatórias.

## 🛠️ O que fazer

1. **Validação real do conteúdo** do upload com `ffprobe`: rejeitar arquivos sem stream de vídeo/áudio, mesmo que a extensão seja `.mp4`. Limitar a duração máxima (`MAX_VIDEO_MINUTES`).
2. **Upload em streaming** para o disco, com limite aplicado durante a leitura (hoje o tamanho só é verificado depois de o arquivo inteiro estar recebido).
3. **Rate limiting** por IP (`slowapi`): ex. 10 uploads/hora.
4. **Autenticação simples** opcional (token no header ou login no Streamlit) quando `APP_ENV=production`.
5. Jobs só podem ser consultados/baixados por quem os criou (token do job devolvido no upload).
6. Atualizar o `@app.on_event("startup")` (descontinuado) para `lifespan`.
7. Revisar CORS e CSP para o cenário com domínio próprio.

## ✅ Critérios de aceite

- [ ] Arquivo `.mp4` falso é rejeitado no upload (não só no worker).
- [ ] Exceder o rate limit retorna 429.

## 🔗 Dependências

Nenhuma específica; pode ser feita a qualquer momento.
