# Guia do ambiente Docker

## 1. Objetivo

Subir localmente todos os serviços do sistema com Docker Compose e GPU NVIDIA, e verificar o ambiente.

## 2. Requisitos

| Item | Requisito |
|---|---|
| Sistema | Windows 11 com Docker Desktop (backend WSL2) |
| GPU | NVIDIA com driver recente; suporte a GPU habilitado no Docker Desktop |
| RAM | `.wslconfig` com `memory=12GB` e `swap=8GB` |
| Disco | Repositório em disco local do Windows; os dados ficam em volumes nomeados, fora de `/mnt/c` |

### 2.1 Preparação do Windows

1. Crie ou edite `%UserProfile%\.wslconfig`:

   ```ini
   [wsl2]
   memory=12GB
   swap=8GB
   ```

2. Aplique: `wsl --shutdown` e reabra o Docker Desktop.
3. Verifique o driver no Windows: `nvidia-smi`.
4. Verifique a GPU no WSL: `wsl nvidia-smi`.
5. Verifique a GPU em contêiner: `docker run --rm --gpus all nvidia/cuda:12.6.3-base-ubuntu24.04 nvidia-smi`.

## 3. Configuração

1. Copie o modelo: `cp infra/.env.example infra/.env`.
2. Preencha `POSTGRES_PASSWORD`, `SENHA_REDIS` e `JWT_SECRET` com valores hexadecimais: `openssl rand -hex 32`.
3. Para o modo de assinatura do Claude, mantenha `ANTHROPIC_API_KEY` vazia. O worker de IA aborta se a variável estiver definida com `CLAUDE_MODE=subscription`.

O arquivo `infra/.env` não é versionado.

## 4. Operação

| Ação | Comando |
|---|---|
| Subir | `docker compose -f infra/docker-compose.yml up -d --build` |
| Estado | `docker compose -f infra/docker-compose.yml ps` |
| Logs | `docker compose -f infra/docker-compose.yml logs -f api` |
| Parar | `docker compose -f infra/docker-compose.yml down` |
| Apagar dados | `docker compose -f infra/docker-compose.yml down -v` (remove os volumes) |

## 5. Serviços

| Serviço | Função | Porta no host |
|---|---|---|
| `api` | FastAPI | 127.0.0.1:8000 |
| `frontend` | Página provisória até a S0 entregar a interface | 127.0.0.1:8080 |
| `worker-gpu` | Fila `gpu` (ASR, NVENC); concorrência 1 | — |
| `worker-cpu` | Filas `cpu` e `celery` (fluxo atual de legendas) | — |
| `worker-ai` | Fila `ai` (provedores externos) | — |
| `beat` | Agendador | — |
| `redis` | Broker, protegido por senha | — |
| `postgres` | Banco de dados | — |
| `ollama` | Modelos locais; `KEEP_ALIVE=0`, um modelo por vez | — |
| `render` | Serviço provisório até a renderização ser implementada | — |

Somente `api` e `frontend` publicam portas, e apenas em `127.0.0.1`.

O `worker-gpu` não tem acesso à internet. Os modelos são baixados pelo `worker-cpu` para o volume `dados` (`HF_HOME=/dados/hf`) e reutilizados pelo `worker-gpu`.

## 6. Verificação

| Verificação | Comando | Resultado esperado |
|---|---|---|
| Saúde dos serviços | `docker compose -f infra/docker-compose.yml ps` | Todos `healthy` |
| API | `curl -i http://127.0.0.1:8000/health` | `200` com cabeçalhos de segurança |
| GPU | `docker compose -f infra/docker-compose.yml exec worker-gpu nvidia-smi` | Tabela com a placa NVIDIA |
| Codificador | `docker compose -f infra/docker-compose.yml exec worker-gpu ffmpeg -hide_banner -encoders` | Lista contém `h264_nvenc` |
| Volumes | `docker volume ls` | `viraliza_dados`, `viraliza_modelos`, `viraliza_redis_dados`, `viraliza_pg_dados`, `viraliza_claude_config` |
| Configuração | `bash scripts/verificar_infra.sh` | `STATUS: OK` |

## 7. Endurecimento aplicado

| Controle | Aplicação |
|---|---|
| Usuário | Não root em todos os serviços |
| Capacidades | `cap_drop: ALL` e `no-new-privileges` |
| Sistema de arquivos | `read_only` com `tmpfs` em `/tmp`; código da imagem pertence ao root |
| Rede | `interna` e `ia` sem saída para a internet; `externa` somente para api, frontend, worker-cpu e worker-ai. O `ollama` só é alcançado por `worker-ai` e `worker-gpu` |
| Recursos | Limite de memória e de processos por serviço |
| Segredos | Obrigatórios no `.env`; ausência impede a subida e nomeia a variável |
| Redis | Senha hexadecimal obrigatória; comandos `FLUSHALL`, `FLUSHDB`, `DEBUG`, `CONFIG` e `MODULE` desativados |
