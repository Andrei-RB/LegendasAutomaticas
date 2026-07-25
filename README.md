<div align="center">

# 🎬 Secure Subtitle Generator AI

**Geração automática de legendas com Inteligência Artificial, arquitetura distribuída e segurança de nível empresarial.**

[![Python 3.11](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Celery](https://img.shields.io/badge/Celery-5.4+-37814A?style=for-the-badge&logo=celery&logoColor=white)](https://docs.celeryq.dev/)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.33+-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docs.docker.com/compose/)
[![OWASP](https://img.shields.io/badge/OWASP-Top%2010-000000?style=for-the-badge&logo=owasp&logoColor=white)](https://owasp.org/)

</div>

---

## 📋 Sobre o Projeto

O **Secure Subtitle Generator AI** é uma plataforma web completa para geração automática de legendas em formato **SRT** a partir de arquivos de vídeo. Desenvolvido com foco em **segurança**, **escalabilidade** e **qualidade de código empresarial**, o projeto utiliza o modelo de transcrição por IA **OpenAI Whisper** (via `faster-whisper`) para entregar resultados precisos com latência otimizada.

Todo o sistema roda em containers **Docker** isolados, eliminando dependências de configuração no sistema operacional do usuário — basta ter o Docker instalado.

### ✨ Funcionalidades Principais

- 📤 **Upload seguro de vídeos** (`.mp4`, `.avi`, `.mov`, `.mkv`) com validação multicamadas.
- 🤖 **Transcrição de áudio para texto** utilizando o modelo Whisper via `faster-whisper` + `ffmpeg`.
- ⚡ **Processamento 100% assíncrono** via fila de tarefas Celery + Redis — sem bloquear a interface.
- 📊 **Acompanhamento em tempo real** do progresso via *long polling* na interface web.
- 📥 **Download direto do arquivo `.srt`** pelo navegador após a conclusão.
- 🔒 **Segurança OWASP/NIST** aplicada na API (CSP, rate limiting, sanitização de inputs, headers seguros).
- 📄 **Logs estruturados em JSON** compatíveis com SIEM (ex.: Elastic Stack, Splunk).

---

## 🏛️ Arquitetura

O projeto segue o padrão **SOA-Ready Modular Monolith**, projetado para escalar para microsserviços quando necessário.

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Docker Network                              │
│                                                                     │
│  ┌──────────────┐    HTTP     ┌──────────────┐   Enqueue   ┌──────┐ │
│  │  Streamlit   │ ──────────► │   FastAPI    │ ──────────► │Redis │ │
│  │  (Frontend)  │             │  (REST API)  │             │Queue │ │
│  │  Port 8501   │ ◄────────── │  Port 8000   │ ◄────────── │:6379 │ │
│  └──────────────┘  Polling    └──────────────┘   Results   └──────┘ │
│                                                               ▲     │
│                                                               │Poll │
│                                                    ┌──────────┴──┐  │
│                                                    │Celery Worker│  │
│                                                    │(Faster-     │  │
│                                                    │ Whisper+    │  │
│                                                    │  ffmpeg)    │  │
│                                                    └─────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
         │                                                │
   localhost:8501                                  localhost:8000
   (Interface Web)                               (API — uso interno)
```

### Serviços Docker

| Serviço | Imagem Base | Responsabilidade | Porta (local) |
|---|---|---|---|
| `redis` | `redis:7-alpine` | Message broker e backend de resultados | Interna |
| `api` | `python:3.11-slim` | Validação, roteamento e orquestração de jobs | `127.0.0.1:8000` |
| `worker` | `python:3.11-slim` | Transcrição de áudio com Whisper em background | Interna |
| `frontend` | `python:3.11-slim` | Interface web (Streamlit) | `127.0.0.1:8501` |

> **Segurança de rede:** A porta do Redis **não é exposta** ao sistema hospedeiro. As portas da API e Frontend estão vinculadas exclusivamente ao `127.0.0.1`, tornando o sistema acessível **somente localmente**.

---

## 🛡️ Segurança

A aplicação implementa um conjunto robusto de controles de segurança:

| Camada | Controles Implementados |
|---|---|
| **API Gateway** | Rate Limiting, CORS restritivo, validação de Content-Type |
| **Upload** | Verificação dupla de extensão + MIME type, limite de 1GB |
| **Headers HTTP** | `Content-Security-Policy`, `X-Frame-Options`, `X-Content-Type-Options` |
| **Logs** | Formato JSON estruturado (NIST-compliant), pronto para ingestão em SIEM |
| **Rede Docker** | Redis e Worker isolados, sem exposição externa de portas internas |
| **Docs API** | Swagger/ReDoc desabilitados em produção (`DEBUG=False`) |

---

## 🚀 Como Executar (Instalação e Uso)

### Pré-requisitos

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalado e em execução.
- Isso é tudo. ✅

### 1. Clone o Repositório

```bash
git clone https://github.com/seu-usuario/legenda_app.git
cd legenda_app
```

### 2. Configure as Variáveis de Ambiente

Copie o arquivo de exemplo e ajuste se necessário (as configurações padrão já funcionam para uso local):

```bash
# Windows (PowerShell)
Copy-Item .env.example .env

# Linux / macOS
cp .env.example .env
```

### 3. Suba os Containers

```bash
docker-compose up --build
```

Na primeira execução, o Docker irá baixar as imagens base e instalar todas as dependências (Python, ffmpeg, etc.). Aguarde a conclusão — isso pode levar alguns minutos.

Você saberá que está pronto quando ver no terminal:

```
legenda_frontend  |   Local URL: http://localhost:8501
legenda_api       | INFO: Application startup complete.
legenda_worker    | celery@... ready.
```

### 4. Acesse a Aplicação

Abra o seu navegador e acesse:

**👉 [http://localhost:8501](http://localhost:8501)**

### 5. Encerrar o Sistema

Para parar todos os containers de forma segura:

```bash
# Ctrl+C no terminal onde rodou o compose, ou:
docker-compose down
```

---

## 📖 Fluxo de Uso

```
1. Acesse http://localhost:8501
         │
         ▼
2. Arraste ou selecione um arquivo de vídeo (.mp4, .avi, .mov, .mkv)
         │
         ▼
3. Clique em "🚀 Iniciar Processamento"
         │
         ▼
4. Acompanhe o progresso em tempo real na barra de status
         │
         ▼
5. Clique em "📁 Baixar Legenda (.srt)" quando concluído
         │
         ▼
6. O arquivo .srt é salvo automaticamente pelo seu navegador
```

---

## 🗂️ Estrutura do Projeto

```
legenda_app/
│
├── app/                        # Código-fonte do Backend (FastAPI)
│   ├── api/                    # Endpoints REST da aplicação
│   │   └── endpoints.py        # Rotas: /upload-video, /status/{id}, /download/{id}
│   ├── core/                   # Configurações, logger e settings
│   │   ├── config.py           # Variáveis de ambiente via Pydantic Settings
│   │   └── logger.py           # Logger JSON estruturado (NIST-compliant)
│   ├── schemas/                # Modelos Pydantic de request/response
│   ├── security/               # Middlewares de segurança (Headers, CORS, Rate Limit)
│   │   └── middleware.py       # Configuração OWASP Top 10
│   ├── services/               # Regras de negócio (processamento de arquivo)
│   ├── workers/                # Tarefas assíncronas Celery
│   │   └── celery_worker.py    # Task de transcrição com Faster-Whisper
│   └── main.py                 # Entrada da aplicação FastAPI
│
├── frontend/                   # Interface Web (Streamlit)
│   └── frontend_app.py         # UI completa: upload, polling, download
│
├── tests/                      # Testes automatizados (pytest)
│
├── outputs/                    # Arquivos .srt gerados (volume Docker)
├── uploads/                    # Vídeos recebidos temporariamente (volume Docker)
├── logs/                       # Logs JSON da aplicação (volume Docker)
│
├── .env                        # Variáveis de ambiente locais (NÃO commitar)
├── .env.example                # Template de configuração
├── .dockerignore               # Arquivos excluídos do build Docker
├── Dockerfile                  # Imagem base unificada para todos os serviços Python
├── docker-compose.yml          # Orquestração dos 4 containers
└── requirements.txt            # Dependências Python
```

---

## ⚙️ Variáveis de Ambiente

| Variável | Padrão | Descrição |
|---|---|---|
| `APP_NAME` | `Secure Subtitle Generator` | Nome da aplicação |
| `APP_ENV` | `development` | Ambiente de execução |
| `DEBUG` | `True` | Habilita docs Swagger e logs detalhados |
| `API_V1_STR` | `/api/v1` | Prefixo base das rotas da API |
| `REDIS_URL` | `redis://redis:6379/0` | Conexão com o broker Redis |
| `UPLOAD_DIR` | `uploads` | Diretório de vídeos recebidos |
| `OUTPUT_DIR` | `outputs` | Diretório dos arquivos `.srt` gerados |
| `LOG_DIR` | `logs` | Diretório dos arquivos de log |
| `MAX_UPLOAD_SIZE` | `1073741824` | Limite de upload em bytes (1 GB) |
| `ALLOWED_EXTENSIONS` | `.mp4,.avi,.mov,.mkv` | Formatos de vídeo aceitos |

---

## 🧪 Testes

Os testes de integração e segurança podem ser executados diretamente dentro do container:

```bash
docker-compose run --rm api pytest tests/ -v
```

---

## 📈 Escalabilidade e Roadmap

O projeto foi arquitetado para crescer sem refatorações disruptivas:

- **Mais Workers:** Basta adicionar réplicas do serviço `worker` no `docker-compose.yml` para paralelizar o processamento de múltiplos vídeos simultaneamente.
- **Migração para Kubernetes:** O serviço `worker` pode ser desacoplado para um Pod com GPU (ex.: NVIDIA) via k8s, escalando a transcrição horizontalmente para workloads massivos.
- **Modelos de IA configuráveis:** A versão do modelo Whisper (`tiny`, `base`, `small`, `medium`, `large`) pode ser parametrizada via variável de ambiente para balancear velocidade vs. precisão.

---

## 🧠 Stack Tecnológica

| Tecnologia | Versão | Uso |
|---|---|---|
| **Python** | 3.11 | Linguagem principal |
| **FastAPI** | >= 0.115 | Framework REST API assíncrono |
| **Uvicorn** | >= 0.30 | Servidor ASGI de alta performance |
| **Celery** | >= 5.4 | Fila de tarefas distribuídas |
| **Redis** | 7 | Message broker e cache de resultados |
| **faster-whisper** | >= 1.0 | Transcrição de áudio com IA (CTranslate2) |
| **Streamlit** | >= 1.33 | Interface web interativa |
| **Pydantic** | >= 2.9 | Validação de dados e settings |
| **Docker Compose** | V2 | Orquestração de containers |
| **ffmpeg** | Sistema | Processamento e decodificação de vídeo |

---

## 📄 Licença

Este projeto está licenciado sob a **MIT License** — sinta-se livre para usar, modificar e distribuir.

---

<div align="center">

Desenvolvido com ❤️ e foco em qualidade de software.

</div>
