# 🎬 LegendasAutomáticas

> Pipeline assíncrono com IA para geração automática de arquivos de legenda **SRT** a partir de vídeos — pensado para criadores de conteúdo, editores de vídeo e produtoras.

---

## 📌 Visão Geral

**LegendasAutomáticas** é uma aplicação web full-stack que transcreve automaticamente o áudio de um vídeo e gera um arquivo de legenda no formato `.srt`, pronto para ser importado em qualquer editor de vídeo (CapCut, DaVinci Resolve, Premiere, etc).

O processamento é feito de forma **assíncrona e não bloqueante**: o vídeo é enviado pelo usuário, enfileirado e processado em background por um worker de IA, com progresso em tempo real na interface.

---

## ✨ Funcionalidades

- 📤 Upload de vídeo via interface web (Streamlit)
- 🤖 Transcrição automática com modelo **Faster-Whisper** (OpenAI Whisper otimizado)
- 📝 Geração de legenda `.srt` **palavra por palavra** (ideal para Reels e Shorts)
- 📊 Progresso em tempo real com polling assíncrono
- 📥 Download direto do arquivo `.srt` gerado
- 🔒 Camada de segurança aplicada em toda a API

---

## 🏗️ Arquitetura

```
┌─────────────────┐     HTTP      ┌──────────────────────────────────┐
│  Frontend       │ ──────────►   │  FastAPI Backend (Uvicorn)       │
│  (Streamlit)    │ ◄──────────   │  /api/v1/upload-video            │
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
| **Frontend**   | Streamlit                           | Interface web de upload e monitoramento        |
| **IA / ML**    | Faster-Whisper (`base`, CPU/int8)   | Transcrição de fala para texto com timestamps |
| **Áudio**      | FFmpeg                              | Extração e conversão de áudio (WAV 16kHz mono) |
| **Filas**      | Celery                              | Processamento assíncrono em background          |
| **Broker**     | Redis                               | Message broker e result backend do Celery      |
| **Validação**  | Pydantic v2 + pydantic-settings     | Schemas e configuração via variáveis de ambiente |
| **Logging**    | python-json-logger + RotatingFileHandler | Logs estruturados em JSON com rotação       |
| **Testes**     | Pytest + HTTPX                      | Testes de integração e cliente HTTP assíncrono |

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

- Python 3.10+
- [Redis](https://redis.io/) rodando em `localhost:6379`
- [FFmpeg](https://ffmpeg.org/) instalado e disponível no `PATH`

### Instalação

```bash
# Clone o repositório
git clone https://github.com/Andrei-RB/LegendasAutomaticas
cd LegendasAutomaticas

# Crie e ative o ambiente virtual
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Instale as dependências
pip install -r requirements.txt

# Configure as variáveis de ambiente
cp .env.example .env
```

### Inicialização dos Serviços

```bash
# 1. Redis
wsl sudo service redis-server start

# 2. Backend FastAPI
.\venv\Scripts\python.exe -m uvicorn app.main:app --port 8000

# 3. Worker Celery (em outro terminal)
.\venv\Scripts\python.exe -m celery -A app.workers.celery_worker worker --pool=solo -l info

# 4. Frontend Streamlit (em outro terminal)
streamlit run frontend/frontend_app.py
```

Acesse: **http://localhost:8501**

---

## 📁 Estrutura do Projeto

```
legenda_app/
├── app/
│   ├── api/            # Endpoints REST (upload, status, download)
│   ├── core/           # Configurações e logger estruturado
│   ├── schemas/        # Modelos Pydantic de request/response
│   ├── security/       # Middleware de headers e validação de upload
│   ├── services/       # Lógica de negócio (áudio + transcrição)
│   └── workers/        # Celery app e tasks assíncronas
├── frontend/           # Interface Streamlit
├── tests/              # Testes automatizados
├── .env.example        # Template de variáveis de ambiente
├── requirements.txt    # Dependências do projeto
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
