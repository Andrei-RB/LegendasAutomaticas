<!-- epic: 🧱 Sprint 0 — Fundação e correções | labels: epic, sprint-0 -->
## 🎯 Objetivo da Sprint

Deixar a base do projeto **estável e preparada para crescer**: corrigir os bugs conhecidos, reorganizar o processamento em **etapas configuráveis** (pipeline) e criar testes + CI. Sem isso, as Sprints seguintes viram remendo em cima de remendo.

## ✅ Definição de pronto (DoD) da Sprint

- [ ] Todos os bugs conhecidos corrigidos (mensagem de limite, erro no status, rota raiz, progresso, limpeza de arquivos).
- [ ] A task do Celery recebe um objeto `options` e executa etapas independentes.
- [ ] Existe um `transcript.json` por job, e o `.srt` é gerado **a partir dele**.
- [ ] `pytest` passa localmente e no GitHub Actions a cada push/PR.
- [ ] O launcher sobe **todos** os serviços, incluindo o frontend.

## 📋 Tarefas

As tarefas estão listadas como sub-issues abaixo.

<!-- issue: [S0] Corrigir mensagem de limite de tamanho no upload (diz 500 MB, limite real é 1 GB) | labels: bug, sprint-0 -->
## 🧩 Contexto

Em `app/security/validation.py`, quando o arquivo passa do limite, a API responde:

```python
detail="Arquivo muito grande. Limite é de 500 MB."
```

Mas o limite configurado em `app/core/config.py` é `MAX_UPLOAD_SIZE = 1 GB`. O usuário recebe uma informação falsa. Além disso, o frontend (`frontend/frontend_app.py`) tem o limite e as extensões **duplicados** em constantes próprias, que podem divergir do backend.

## 🛠️ O que fazer

1. Gerar a mensagem a partir de `settings.MAX_UPLOAD_SIZE`, sem número fixo no texto.
2. Criar um endpoint `GET /api/v1/config/limits` que devolve `{ "max_upload_bytes": ..., "allowed_extensions": [...] }`.
3. No frontend, buscar esses valores na inicialização (com fallback para os valores atuais se a API estiver fora do ar).

## 📁 Arquivos afetados

- `app/security/validation.py`
- `app/api/endpoints.py`
- `frontend/frontend_app.py`
- `tests/test_api.py`

## 💡 Exemplo de código

```python
# validation.py
limite_mb = settings.MAX_UPLOAD_SIZE // (1024 * 1024)
raise HTTPException(
    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
    detail=f"Arquivo muito grande. O limite é de {limite_mb} MB.",
)
```

```python
# endpoints.py
@router.get("/config/limits")
async def get_limits():
    return {
        "max_upload_bytes": settings.MAX_UPLOAD_SIZE,
        "allowed_extensions": settings.allowed_extensions_list,
    }
```

## ✅ Critérios de aceite

- [ ] A mensagem de erro mostra o limite real, calculado a partir da configuração.
- [ ] Alterar `MAX_UPLOAD_SIZE` no `.env` muda a mensagem **e** a validação do frontend, sem mexer no código.
- [ ] Endpoint `/config/limits` coberto por teste.

## 🧪 Como testar

1. Coloque `MAX_UPLOAD_SIZE=1048576` (1 MB) no `.env`.
2. Envie um vídeo de 2 MB e veja a mensagem "O limite é de 1 MB".
3. Rode `pytest`.

## 🔗 Dependências

Nenhuma.

<!-- issue: [S0] Corrigir mensagem de erro exibida no /status quando o job falha | labels: bug, sprint-0 -->
## 🧩 Contexto

Em `app/workers/tasks.py`, quando dá erro, a task faz:

```python
self.update_state(state='FAILURE', meta={'progress': 0, 'status': f'Erro: {str(e)}'})
raise Ignore()
```

E em `app/api/endpoints.py` o `/status` faz:

```python
error_msg = str(task.info) if task.info else "Erro de execução."
```

Como `task.info` é o **dicionário** `meta`, o usuário vê algo como `{'progress': 0, 'status': 'Erro: ...'}` em vez de uma mensagem limpa. Além disso, mensagens internas de exceção (caminhos de arquivo, stack) podem vazar para o usuário (OWASP: *Information Exposure*).

## 🛠️ O que fazer

1. Padronizar o `meta` de falha: `{"progress": 0, "status": "FAILURE", "error": "<mensagem amigável>", "error_code": "<código>"}`.
2. Criar exceções de domínio com mensagens amigáveis, por exemplo `PipelineError(code, user_message)`:
   - `AUDIO_EXTRACTION_FAILED`: "Não foi possível ler o áudio deste vídeo."
   - `TRANSCRIPTION_FAILED`: "A transcrição falhou. Tente novamente."
   - `TIMEOUT`: "O processamento passou do tempo limite."
   - `UNKNOWN`: "Erro inesperado. Tente novamente."
3. No `/status`, ler `meta["error"]` quando `task.info` for dict. Se não for dict, usar a mensagem genérica.
4. Registrar a exceção completa **só no log**, nunca na resposta.

## 📁 Arquivos afetados

- `app/workers/tasks.py`
- `app/api/endpoints.py`
- `app/schemas/job.py` (campo opcional `error_code`)
- novo: `app/core/errors.py`

## 💡 Exemplo de código

```python
# app/core/errors.py
class PipelineError(Exception):
    def __init__(self, code: str, user_message: str):
        super().__init__(user_message)
        self.code = code
        self.user_message = user_message
```

```python
# endpoints.py (trecho do /status)
elif task.state == "FAILURE":
    info = task.info if isinstance(task.info, dict) else {}
    return JobStatus(
        job_id=job_id, status="FAILURE", progress=0,
        error=info.get("error", "Erro inesperado. Tente novamente."),
        error_code=info.get("error_code", "UNKNOWN"),
    )
```

## ✅ Critérios de aceite

- [ ] O frontend mostra apenas uma frase amigável quando o job falha.
- [ ] O log (`logs/`) contém o erro técnico completo, com `job_id`.
- [ ] Teste com um `.mp4` corrompido retorna `error_code = AUDIO_EXTRACTION_FAILED`.

## 🧪 Como testar

1. Crie um arquivo falso: `echo "nao sou video" > falso.mp4`.
2. Faça o upload e aguarde: deve aparecer "Não foi possível ler o áudio deste vídeo."

## 🔗 Dependências

Nenhuma.

<!-- issue: [S0] Corrigir rota raiz "/" e o teste test_api_status (falta index.html) + criar /health | labels: bug, testes, sprint-0 -->
## 🧩 Contexto

`app/main.py` monta a pasta `frontend/` como site estático na raiz:

```python
app.mount("/", StaticFiles(directory="frontend", html=True), name="static")
```

Só que o frontend é **Streamlit** (`frontend_app.py`), não HTML. Não existe `index.html`, então `GET /` responde **404** e o teste `test_api_status` (que espera 200) falha. Pior: o servidor estático expõe o código-fonte do frontend (`GET /frontend_app.py`).

## 🛠️ O que fazer

1. Remover o `app.mount("/", StaticFiles(...))`.
2. Criar `GET /api/v1/health` que responde `{"status": "ok", "redis": true/false, "ffmpeg": true/false}`.
   - Redis: `celery_app.control.ping(timeout=1)` ou `redis.Redis.from_url(...).ping()`.
   - FFmpeg: `shutil.which("ffmpeg") is not None`.
3. Opcional: `GET /` redireciona para a URL do Streamlit (`FRONTEND_URL`, nova configuração) ou responde um JSON simples com o nome da API.
4. Atualizar `test_api_status` para chamar `/api/v1/health`.
5. Remover imports não usados em `main.py` (`os`, `FileResponse`).

## 📁 Arquivos afetados

- `app/main.py`
- `app/api/endpoints.py`
- `app/core/config.py`
- `tests/test_api.py`

## ✅ Critérios de aceite

- [ ] `GET /frontend_app.py` responde 404 (código-fonte não é mais exposto).
- [ ] `GET /api/v1/health` responde 200 com o estado das dependências.
- [ ] `pytest` passa sem Redis rodando (o health devolve `redis: false`, sem quebrar).

## 🧪 Como testar

`pytest -v` e `curl http://localhost:8000/api/v1/health`

## 🔗 Dependências

Nenhuma.

<!-- issue: [S0] Limpeza automática de arquivos antigos (outputs/ e uploads/ órfãos) | labels: enhancement, infra, sprint-0 -->
## 🧩 Contexto

A task apaga o vídeo e o WAV depois de processar, mas:

- Os `.srt` em `outputs/` **nunca são apagados**. O disco enche com o tempo.
- O resultado no Redis expira em 1 h (`result_expires=3600`), então depois disso o `/status` não acha mais o job, mas o arquivo continua lá.
- Se o worker morrer no meio, o vídeo fica órfão em `uploads/`.

Com as próximas Sprints (vídeos renderizados, clipes), o volume vai crescer **muito**.

## 🛠️ O que fazer

1. Nova configuração `RETENTION_HOURS` (padrão: 24).
2. Organizar a saída **por job**: `outputs/<job_id>/` (`legenda.srt`, `transcript.json` e, no futuro, `legenda.ass`, `video_final.mp4`...). Atualizar o download.
3. Criar a task `cleanup_old_files` que apaga pastas/arquivos com `mtime` mais antigo que `RETENTION_HOURS`, em `outputs/` e `uploads/`.
4. Agendar com **Celery Beat** (a cada 1 h). Alternativa sem Beat: rodar a limpeza no `startup` da API e a cada N uploads.
5. Alinhar `result_expires` com `RETENTION_HOURS`.
6. Atualizar o `launcher.py` para subir o Beat (ou usar `celery worker -B` em desenvolvimento).

## 📁 Arquivos afetados

- `app/core/config.py`
- `app/workers/celery_worker.py` (`beat_schedule`)
- `app/workers/tasks.py`
- `app/api/endpoints.py` (novo caminho do download)
- `launcher.py`

## 💡 Exemplo de código

```python
# celery_worker.py
celery_app.conf.beat_schedule = {
    "limpeza-de-arquivos": {"task": "cleanup_old_files", "schedule": 3600.0},
}
celery_app.conf.result_expires = settings.RETENTION_HOURS * 3600
```

```python
# tasks.py
@celery_app.task(name="cleanup_old_files")
def cleanup_old_files():
    limite = time.time() - settings.RETENTION_HOURS * 3600
    for base in (settings.OUTPUT_DIR, settings.UPLOAD_DIR):
        for nome in os.listdir(base):
            caminho = os.path.join(base, nome)
            if os.path.getmtime(caminho) < limite:
                shutil.rmtree(caminho) if os.path.isdir(caminho) else os.remove(caminho)
```

## ✅ Critérios de aceite

- [ ] Arquivos mais velhos que `RETENTION_HOURS` são apagados automaticamente.
- [ ] Cada job tem a própria pasta em `outputs/<job_id>/`.
- [ ] O download continua funcionando, com validação contra *path traversal*.
- [ ] Teste unitário da limpeza usando `tmp_path` e `os.utime` para "envelhecer" arquivos.

## 🔗 Dependências

Nenhuma.

<!-- issue: [S0] Barra de progresso contínua e etapas nomeadas | labels: enhancement, sprint-0 -->
## 🧩 Contexto

Hoje o progresso vai: 5% → 20% → **pula para 30%** (início da transcrição) → 90% → 100%. Os percentuais estão espalhados "na mão" em `tasks.py` e `transcription_service.py`. Quando novas etapas entrarem (Gemini, cortes, render), isso vira bagunça.

## 🛠️ O que fazer

1. Criar um `ProgressReporter` que recebe a lista de etapas **ativas** do job com pesos, por exemplo:
   - `extract_audio` 10, `transcribe` 50, `gemini_review` 15, `cuts` 10, `render` 15.
2. Cada etapa reporta o próprio avanço de 0.0 a 1.0, e o reporter converte para o percentual global.
3. O `meta` passa a ter `progress`, `step` (código da etapa) e `message` (texto amigável).
4. O frontend mostra a barra de progresso **e** o nome da etapa atual.
5. Limitar as atualizações no Redis (no máximo 1 a cada ~0,5 s) para não sobrecarregar.

## 📁 Arquivos afetados

- novo: `app/pipeline/progress.py`
- `app/workers/tasks.py`
- `app/services/transcription_service.py`
- `app/schemas/job.py` (campos `step`, `message`)
- `frontend/frontend_app.py`

## 💡 Exemplo de código

```python
class ProgressReporter:
    def __init__(self, task, steps: dict[str, int]):
        self.task, self.steps = task, steps
        self.total = sum(steps.values())
        self.done = 0
        self._last = 0.0

    def update(self, step: str, fraction: float, message: str):
        if time.monotonic() - self._last < 0.5 and fraction < 1:
            return
        self._last = time.monotonic()
        pct = int((self.done + self.steps[step] * fraction) / self.total * 100)
        self.task.update_state(state="PROCESSING",
                               meta={"progress": min(pct, 99), "step": step, "message": message})

    def finish_step(self, step: str):
        self.done += self.steps[step]
```

## ✅ Critérios de aceite

- [ ] O progresso nunca retrocede e não tem saltos maiores que ~10% sem motivo.
- [ ] Etapas desligadas não "ocupam" percentual.
- [ ] O frontend exibe a etapa atual, por exemplo "Transcrevendo... (45s de 120s)".

## 🔗 Dependências

Faça junto com a tarefa "Refatorar processamento em pipeline de etapas".

<!-- issue: [S0] Refatorar processamento em pipeline de etapas + opções por job + transcript.json | labels: enhancement, infra, sprint-0 -->
## 🧩 Contexto

Hoje `process_video_task` faz tudo direto: extrai o áudio, transcreve e já escreve o `.srt` dentro do `transcription_service`. Para adicionar Gemini, cortes, temas e render, precisamos de:

1. **Opções por job**, que o usuário escolhe no frontend.
2. **Etapas independentes**, que podem ser ligadas e desligadas.
3. Uma **representação intermediária** (`transcript.json`) de onde todos os formatos de saída são gerados.

**Esta é a tarefa mais importante da Sprint 0.** Todas as outras Sprints dependem dela.

## 🛠️ O que fazer

### 1. Schema de opções (`app/schemas/options.py`)

```python
class JobOptions(BaseModel):
    language: str = "pt"
    caption_mode: Literal["word", "short", "sentence"] = "short"
    max_words_per_caption: int = Field(3, ge=1, le=12)
    vocabulary: list[str] = []            # Sprint 1
    ai_review: bool = False               # Sprint 2
    emojis: Literal["none", "few", "many"] = "none"
    highlight_keywords: bool = False
    theme: str | None = None              # Sprint 3
    burn_subtitles: bool = False
    remove_silences: bool = False         # Sprint 4
    remove_fillers: bool = False
    # ... demais opções entram nas próximas Sprints
```

### 2. Upload recebe as opções

`POST /upload-video` recebe um campo de formulário `options` (string JSON), validado com `JobOptions.model_validate_json(...)`. Se for inválido: **422** com mensagem clara. Se não for enviado: usa os padrões.

### 3. Formato do `transcript.json` (fonte única da verdade)

```json
{
  "version": 1,
  "job_id": "…",
  "language": "pt",
  "duration": 123.4,
  "words": [
    {"i": 0, "text": "Hoje", "start": 0.52, "end": 0.80, "prob": 0.97, "emoji": null, "highlight": false},
    {"i": 1, "text": "vou",  "start": 0.80, "end": 0.95, "prob": 0.95, "emoji": null, "highlight": false}
  ],
  "segments": [{"start": 0.52, "end": 3.1, "word_range": [0, 9]}],
  "cuts": []
}
```

### 4. Estrutura de pastas proposta

```
app/pipeline/
  __init__.py
  context.py        # JobContext: job_id, paths, options, transcript, reporter
  runner.py         # executa a lista de etapas na ordem
  steps/
    extract_audio.py
    transcribe.py     # só gera words/segments no transcript (não escreve SRT)
    export_srt.py     # lê transcript -> legenda.srt
app/models/transcript.py   # dataclasses/pydantic de Word, Segment, Transcript + load/save
```

### 5. Runner

```python
STEPS = [
    ("extract_audio", always),
    ("transcribe", always),
    ("gemini_review", lambda o: o.ai_review),     # Sprint 2
    ("cuts", lambda o: o.remove_silences or o.remove_fillers),  # Sprint 4
    ("export_srt", always),
    ("export_ass", lambda o: o.theme is not None),  # Sprint 3
    ("render", lambda o: o.burn_subtitles),         # Sprint 3
]
```

### 6. Frontend

Por enquanto, só enviar `options` com os padrões. O painel de opções completo entra quando cada feature for criada.

## 📁 Arquivos afetados

- novos: `app/schemas/options.py`, `app/models/transcript.py`, `app/pipeline/**`
- `app/workers/tasks.py` (a task vira um "runner")
- `app/services/transcription_service.py` (devolve as palavras, não escreve arquivo)
- `app/api/endpoints.py`
- `frontend/frontend_app.py`

## ✅ Critérios de aceite

- [ ] Com as opções padrão, o resultado final (`.srt`) é **equivalente** ao atual (teste de regressão).
- [ ] `outputs/<job_id>/transcript.json` é criado e segue o formato acima.
- [ ] As opções são salvas junto do job (`outputs/<job_id>/options.json`).
- [ ] Enviar `options` inválido retorna 422.
- [ ] Adicionar uma etapa nova exige apenas: criar o arquivo em `steps/` e registrar no runner.
- [ ] Testes unitários: `export_srt` a partir de um transcript fixo (sem Whisper).

## 🔗 Dependências

Nenhuma. **Bloqueia** praticamente todas as tarefas das Sprints 1 a 7.

<!-- issue: [S0] Testes unitários base + GitHub Actions (pytest + ruff) | labels: testes, infra, sprint-0 -->
## 🧩 Contexto

Hoje existem só 3 testes de API. Com o pipeline crescendo, é fácil quebrar algo sem perceber. Precisamos de testes rápidos (sem Whisper, sem FFmpeg real) rodando automaticamente a cada push.

## 🛠️ O que fazer

1. Separar as dependências: `requirements.txt` (app) e `requirements-dev.txt` (`pytest`, `pytest-cov`, `ruff`, `jiwer`).
2. Criar `tests/unit/` com testes para:
   - `format_timestamp` (0 s, 59.999 s, 3600 s, arredondamento dos milissegundos);
   - geração de SRT a partir de um `transcript.json` de exemplo (`tests/fixtures/transcript_exemplo.json`);
   - validação de `JobOptions`;
   - validação de upload (extensão, tamanho, nome malicioso como `../../etc/passwd.mp4`).
3. Mockar Celery nos testes de API (`process_video_task.apply_async` via `monkeypatch`), para não precisar de Redis.
4. Marcar testes lentos/reais com `@pytest.mark.slow` (Whisper/FFmpeg) e pulá-los no CI por padrão.
5. Criar `.github/workflows/ci.yml`:
   - Python 3.11, cache do pip;
   - `ruff check .`;
   - `pytest -m "not slow" --cov=app`.
6. Adicionar `pyproject.toml` com a configuração do ruff e do pytest.

## 💡 Exemplo de CI

```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11", cache: pip }
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - run: ruff check .
      - run: pytest -m "not slow" --cov=app
```

## ✅ Critérios de aceite

- [ ] `pytest -m "not slow"` roda em menos de 30 s, sem Redis/FFmpeg.
- [ ] CI verde no GitHub a cada push e PR.
- [ ] Badge de CI no README.

## 🔗 Dependências

Idealmente depois do pipeline (para testar `export_srt`), mas pode começar antes.

<!-- issue: [S0] Launcher deve subir também o frontend (Streamlit) e funcionar fora do Windows | labels: bug, infra, sprint-0 -->
## 🧩 Contexto

O `launcher.py` sobe Redis (WSL), FastAPI e Celery, mas **não sobe o Streamlit**. O usuário ainda precisa abrir outro terminal e rodar `streamlit run frontend/frontend_app.py` (como descrito em `como-usar-commands.txt`). Além disso:

- Os comandos do Redis são fixos para WSL (`wsl sudo service redis-server start`), o que quebra no Linux e no macOS.
- O `wait_for_port` do Redis pode dar falso positivo/negativo, porque o processo `wsl ... start` termina logo.

## 🛠️ O que fazer

1. Adicionar o serviço `STREAMLIT`: `[PYTHON_BIN, "-m", "streamlit", "run", "frontend/frontend_app.py", "--server.port", "8501"]` e aguardar a porta 8501.
2. Abrir o navegador automaticamente em `http://localhost:8501` (`webbrowser.open`) quando tudo estiver online.
3. Detectar o sistema operacional:
   - Windows: manter o WSL;
   - Linux/macOS: `redis-server --daemonize yes` (ou pular se a porta 6379 já estiver em uso **pelo Redis**).
4. Se o Redis já estiver rodando, **reutilizar** em vez de abortar com erro de porta em uso.
5. Subir o Celery Beat (da tarefa de limpeza), se existir.
6. Atualizar `como-usar-commands.txt` e o README.

## 📁 Arquivos afetados

- `launcher.py`
- `como-usar-commands.txt`
- `README.md`

## ✅ Critérios de aceite

- [ ] `python launcher.py` sobe tudo e abre o navegador no app.
- [ ] Ctrl+C encerra todos os processos, incluindo o Streamlit.
- [ ] Funciona no Windows (WSL) e no Linux.

## 🔗 Dependências

Nenhuma (a parte do Beat depende da tarefa de limpeza).
