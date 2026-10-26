# 🎬 LegendasAutomáticas

[![CI](https://github.com/Andrei-RB/LegendasAutomaticas/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Andrei-RB/LegendasAutomaticas/actions/workflows/ci.yml)

> 🚧 **v2 em construção:** o projeto está evoluindo para um estúdio de cortes virais com legendas e textos de postagem. Veja o [roadmap](docs/sprints/00-roadmap.md) e o [plano](docs/plano-v2.md). A reorganização em monorepo (`backend/`) está concluída; a interface web será recriada na issue #17, e o ambiente Docker está descrito em [docs/guia-ambiente.md](docs/guia-ambiente.md). O conteúdo abaixo descreve a v1 atual.

> 🔒 **Antes do primeiro commit:** rode `bash scripts/instalar_hooks.sh`. Regras de autoria em [CLAUDE.md](CLAUDE.md), seção 4.1.

> Pipeline assíncrono com IA para geração automática de arquivos de legenda **SRT** a partir de vídeos — pensado para criadores de conteúdo, editores de vídeo e produtoras.

---

## 📌 Visão Geral

**LegendasAutomáticas** é uma aplicação web full-stack que transcreve automaticamente o áudio de um vídeo e gera um arquivo de legenda no formato `.srt`, pronto para ser importado em qualquer editor de vídeo (CapCut, DaVinci Resolve, Premiere, etc).

O processamento é feito de forma **assíncrona e não bloqueante**: o vídeo é enviado pelo usuário, enfileirado e processado em background por um worker de IA, com progresso em tempo real na interface.

---

## ✨ Funcionalidades

- 📤 Upload de vídeo via API REST (a interface web volta com a v2)
- 🤖 Transcrição automática com modelo **Faster-Whisper** (OpenAI Whisper otimizado)
- 📝 Geração de legenda `.srt` **palavra por palavra** (ideal para Reels e Shorts)
- 📊 Progresso em tempo real com polling assíncrono
- 📥 Download direto do arquivo `.srt` gerado
- 🔒 Camada de segurança aplicada em toda a API

---

## 🏗️ Arquitetura

```
┌─────────────────┐     HTTP      ┌──────────────────────────────────┐
│  Cliente HTTP   │ ──────────►   │  FastAPI Backend (Uvicorn)       │
│  (curl / UI v2) │ ◄──────────   │  /health  /api/v1/upload-video   │
└─────────────────┘               │  /api/v1/status/{job_id}         │
                                  │  /api/v1/download/{job_id}       │
                                  └───────────────┬──────────────────┘
                                                  │ Enfileira Task
                                                  ▼
                                 ┌──────────────────────────────────┐
                                 │  Celery Worker                   │
                                 │  ├── FFmpeg → extrai áudio (WAV) │
                                 │  └── Faster-Whisper → gera .srt  │
                                 └───────────────┬──────────────────┘
                                                 │ Broker / Backend
                                                 ▼
                                         ┌──────────────┐
                                         │     Redis    │
                                         └──────────────┘
```

---

## 🛠️ Stack Tecnológica

| Camada         | Tecnologia                          | Função                                         |
|----------------|-------------------------------------|------------------------------------------------|
| **Backend**    | FastAPI + Uvicorn                   | API REST assíncrona e servidor ASGI            |
| **IA / ML**    | Faster-Whisper (`base`, CPU/int8)   | Transcrição de fala para texto com timestamps |
| **Áudio**      | FFmpeg                              | Extração e conversão de áudio (WAV 16kHz mono) |
| **Filas**      | Celery                              | Processamento assíncrono em background          |
| **Broker**     | Redis                               | Message broker e result backend do Celery      |
| **Validação**  | Pydantic v2 + pydantic-settings     | Schemas e configuração via variáveis de ambiente |
| **Logging**    | python-json-logger + RotatingFileHandler | Logs estruturados em JSON com rotação       |
| **Testes**     | Pytest + HTTPX                      | Testes de integração e cliente HTTP assíncrono |
| **Qualidade**  | Ruff                                | Lint e formatação                              |

---

## 🔐 Segurança

A aplicação foi construída com referências às diretrizes **OWASP** e **NIST**:

| Camada                    | Medida Aplicada                                                                 |
|---------------------------|---------------------------------------------------------------------------------|
| **Cabeçalhos HTTP**       | `CSP`, `X-Frame-Options: DENY`, `X-Content-Type-Options`, `HSTS`, `Referrer-Policy`, `Permissions-Policy` |
| **Upload de Arquivo**     | Validação de extensão (whitelist), verificação de tamanho (limite 1 GB), sanitização de nome (`os.path.basename`) contra Path Traversal |
| **Identificadores**       | UUIDs aleatórios como nome de arquivo — impede colisão e enumeração            |
| **Download**              | Validação estrita do `job_id` (alfanumérico + hífen) contra Directory Traversal |
| **Injeção de Comando**    | FFmpeg executado via `subprocess` com lista de argumentos — nunca via shell string |
| **API Docs**              | OpenAPI/Swagger/ReDoc desativados em modo produção (`DEBUG=False`)              |
| **Limpeza de Disco**      | Arquivos temporários (vídeo + áudio) removidos após processamento (NIST ISMS)  |
| **Variáveis Sensíveis**   | Configuração via `.env` (nunca versionado) com `.env.example` como referência  |
| **CORS**                  | Configurável via ambiente; restrito a métodos necessários (`GET`, `POST`, `OPTIONS`) |

---

## 🚀 Como Executar Localmente

### Pré-requisitos

- Python 3.12
- [Redis](https://redis.io/) rodando em `localhost:6379`
- [FFmpeg](https://ffmpeg.org/) instalado e disponível no `PATH`

### Instalação

```bash
git clone https://github.com/Andrei-RB/LegendasAutomaticas
cd LegendasAutomaticas/backend

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
```

### Inicialização dos Serviços

Execute em `backend/`:

```bash
# API
python -m uvicorn app.main:app --port 8000 --no-server-header

# Worker Celery (outro terminal)
python -m celery -A app.workers.celery_app worker --pool=solo -l info
```

Verificação: `curl -s http://127.0.0.1:8000/health` retorna `{"status":"healthy"}`.

### Variáveis de Ambiente

Definidas em `backend/.env` (não versionado) ou no ambiente.

| Variável | Padrão | Função |
|---|---|---|
| `DEBUG` | `false` | Habilita `/docs` e `/redoc` |
| `REDIS_URL` | `redis://localhost:6379/0` | Broker e resultado do Celery |
| `MAX_UPLOAD_SIZE` | `1073741824` (1 GB) | Limite de upload em bytes |
| `ALLOWED_EXTENSIONS` | `.mp4,.avi,.mov,.mkv` | Extensões aceitas |
| `CORS_ORIGINS` | vazio | Origens extras, separadas por vírgula |

### Verificações

```bash
ruff check backend && ruff format --check backend
pytest backend -m "not lento"
```

---

## 📁 Estrutura do Projeto

```
├── backend/
│   ├── app/
│   │   ├── api/v1/         # Endpoints REST (upload, status, download)
│   │   ├── nucleo/         # Configuração, logger, validação e cabeçalhos de segurança
│   │   ├── esquemas/       # Modelos Pydantic de request/response
│   │   ├── midia/          # FFmpeg, SRT e transcrição
│   │   ├── workers/        # Celery app e tarefas assíncronas
│   │   ├── modelos/ ia/ pipeline/   # Reservados para as próximas issues
│   │   └── main.py
│   ├── testes/             # Testes automatizados
│   ├── pyproject.toml      # Configuração de ruff e pytest
│   └── requirements*.txt   # Dependências
├── frontend/ infra/ pacotes/ render/ recursos/   # Reservados (S0 e S1)
├── docs/                   # Plano v2 e sprints
└── README.md
```

---

## 📄 Sobre o Formato SRT Gerado

O arquivo `.srt` gerado segue o padrão universal de legendas e é compatível com qualquer editor de vídeo moderno. O modo **palavra por palavra** posiciona cada palavra individualmente com seu timestamp exato — perfeito para criação de legendas dinâmicas em formato Reels/Shorts.

```
1
00:00:01,280 --> 00:00:01,520
Olá

2
00:00:01,520 --> 00:00:01,840
mundo
```

---

## 📜 Licença

Distribuído sob a licença [MIT](LICENSE).
