# Secure Subtitle Generator AI

Um sistema avançado, seguro e distribuído projetado via Monolito Modular, focando na premissa de Software Orientado a Serviços (SOA), permitindo processamento assíncrono para transcrição massiva de mímicas a voz (.srt).

## 🚀 Arquitetura (SOA-Prepared Monolith)

1. **Frontend Minimalista/Moderno** que comunica com Rest API.
2. **Backend FastAPI** validador com robustez e mitigação nativa do OWASP Top 10 (Rate limits, Input sanitation).
3. **Queue Manager Redis + Celery** processando tarefas complexas em background (FFMpeg e Faster Whisper).

### 🔐 Segurança
O software baseia-se num framework estrito: Strict Headers CSP/X-Frame, restrição massiva de uploads com verificação lógica, rotação de logger formato JSON (NIST complient compliance para SIEM rules).

---

## 🛠 Pré-requisitos (Instalações OBRIGATÓRIAS)

### 1. Sistema & Ferramentas
Você precisará ter instalado:
1. **Python** >= 3.10
2. **FFmpeg**: O sistema usa o ffmpeg global. Instale via scoop no windows, ou baixe e adicione na variável (PATH): `choco install ffmpeg` ou via download manual (adicione a pasta bin ao "Environment Variables" > "Path"). Verifique executando `ffmpeg -version` no terminal.
3. **Redis**: Banco em memoria. No Windows nativamente:
   - Baixe as releases compativeis do nicolas (ou execute num WSL/Docker). `choco install redis-64`.
   - Inicialize o servidor rodando em background: `redis-server` (Verifique na 6379 port).

### 2. Ambientes de Configuração
Crie um virtual environment nativo:
```powershell
python -m venv venv
.\venv\Scripts\activate
```

Instale os artefatos restritos:
```powershell
pip install -r requirements.txt
```

---

## 🚦 Executando o Projeto

O sistema opera de forma dual. Um terminal pra API, outro pro Worker.

### 1. Inicie a API (Terminal 1)
Estando com o ambiente virtual ativado na pasta raiz:
```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
> O frontend ficará ativo em `http://localhost:8000/`. Acesse pelo navegador e aproveite a interface para Drop and Upload de vídeos assíncronos.

### 2. Inicie o Worker Celery (Terminal 2)
Ative a venv neste segundo terminal. No windows use `--pool=solo` devido à limitação nativa com sockets unix em threads Python e o celery core:
```powershell
python -m celery -A app.workers.celery_worker worker --pool=solo -l info
```

---

## 🧩 Testes e Auditorias
Execute os testes nativos para auditar as regras de segurança básicas e validação do fluxo:
```powershell
pytest tests/
```

## 🧠 Extensão e Escalabilidade SaaS
Se houver a premissa de transição para microserviços (SaaS global), basta destacar a pasta `/app/workers/` para um Pod independente via k8s, rodando o Celery num hardware GPU intensivo. A API rest se mantém em containers HTTP simples e comunicará o fluxo exclusivamente via Redis Message broker. Restrito e limpo!
