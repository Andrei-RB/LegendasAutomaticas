#!/usr/bin/env bash
# Verifica a infraestrutura Docker sem GPU: sintaxe, segredos, endurecimento e entrypoint.
set -u
cd "$(dirname "$0")/.."

COMPOSE=(docker compose -f infra/docker-compose.yml)
OBRIGATORIAS=(POSTGRES_PASSWORD POSTGRES_APP_PASSWORD SENHA_REDIS JWT_SECRET)
falhas=0
PY=python3
$PY -c "" 2>/dev/null || PY=python

falhar() { echo "FALHA: $*"; falhas=$((falhas + 1)); }

env_completo=$(mktemp)
trap 'rm -f "$env_completo" "${env_parcial:-}" "${cfg_json:-}"' EXIT
for v in "${OBRIGATORIAS[@]}"; do echo "$v=valor_de_teste_0123456789abcdef" >> "$env_completo"; done

echo "[1] compose válido"
"${COMPOSE[@]}" --env-file "$env_completo" config -q || falhar "docker compose config -q"

echo "[2] variável obrigatória ausente nomeia o erro"
for faltante in "${OBRIGATORIAS[@]}"; do
  env_parcial=$(mktemp)
  grep -v "^$faltante=" "$env_completo" > "$env_parcial"
  saida=$("${COMPOSE[@]}" --env-file "$env_parcial" config -q 2>&1) && falhar "subiu sem $faltante"
  echo "$saida" | grep -q "$faltante" || falhar "a mensagem não nomeia $faltante"
done

echo "[3] sem segredos padrão nem caminhos do Windows"
git grep -n "ChaveSegura" -- infra/ && falhar "senha padrão em infra/"
git grep -n "/mnt/c" -- infra/ && falhar "/mnt/c em infra/"

echo "[4] endurecimento dos serviços"
cfg_json=$(mktemp)
"${COMPOSE[@]}" --env-file "$env_completo" config --format json > "$cfg_json" || falhar "config --format json"
$PY -I - "$cfg_json" <<'PYTHON' || falhas=$((falhas + 1))
import json, sys
cfg = json.load(open(sys.argv[1], encoding='utf-8'))
erros = []
for nome, s in cfg["services"].items():
    if s.get("cap_drop") != ["ALL"]:
        erros.append(f"{nome}: cap_drop deve ser [ALL]")
    if "no-new-privileges:true" not in s.get("security_opt", []):
        erros.append(f"{nome}: falta no-new-privileges")
    if not s.get("read_only"):
        erros.append(f"{nome}: read_only ausente")
    if s.get("privileged"):
        erros.append(f"{nome}: privileged")
    for chave in ("cap_add", "devices", "userns_mode"):
        if s.get(chave):
            erros.append(f"{nome}: {chave} não permitido")
    for chave in ("network_mode", "pid", "ipc"):
        if s.get(chave) == "host":
            erros.append(f"{nome}: {chave}=host")
    if any("unconfined" in o for o in s.get("security_opt", [])):
        erros.append(f"{nome}: security_opt unconfined")
    if not s.get("healthcheck") and s.get("restart") != "no":
        erros.append(f"{nome}: sem healthcheck")
    if not s.get("mem_limit") and not s.get("deploy", {}).get("resources", {}).get("limits", {}).get("memory"):
        erros.append(f"{nome}: sem limite de memória")
    if not s.get("pids_limit"):
        erros.append(f"{nome}: sem pids_limit")
    if str(s.get("user", "root")).split(":")[0] in ("", "0", "root"):
        erros.append(f"{nome}: executa como root")
    for p in s.get("ports", []):
        if p.get("host_ip") != "127.0.0.1":
            erros.append(f"{nome}: porta publicada fora de 127.0.0.1")
    for v in s.get("volumes", []):
        if v.get("type") == "bind":
            erros.append(f"{nome}: bind mount {v.get('source')}")
for nome in ("migrar", "api", "worker-gpu", "worker-cpu", "worker-ai", "beat", "redis", "postgres", "ollama", "render", "frontend"):
    if nome not in cfg["services"]:
        erros.append(f"serviço ausente: {nome}")
for nome in ("worker-gpu", "ollama"):
    s = cfg["services"].get(nome, {})
    devs = s.get("deploy", {}).get("resources", {}).get("reservations", {}).get("devices", [])
    if not any(d.get("driver") == "nvidia" for d in devs):
        erros.append(f"{nome}: sem reserva de GPU")
    caps = s.get("environment", {}).get("NVIDIA_DRIVER_CAPABILITIES", "")
    if "video" not in caps.split(","):
        erros.append(f"{nome}: NVIDIA_DRIVER_CAPABILITIES sem video")
for nome, s in cfg["services"].items():
    url = s.get("environment", {}).get("DATABASE_URL", "")
    usuario = url.split("://", 1)[-1].split(":", 1)[0] if url else ""
    esperado = "viraliza" if nome == "migrar" else "viraliza_app" if url else ""
    if usuario != esperado:
        erros.append(f"{nome}: DATABASE_URL deve usar o papel '{esperado or 'nenhum'}'")
env_ollama = cfg["services"].get("ollama", {}).get("environment", {})
if env_ollama.get("OLLAMA_KEEP_ALIVE") != "0" or env_ollama.get("OLLAMA_MAX_LOADED_MODELS") != "1":
    erros.append("ollama: KEEP_ALIVE=0 e MAX_LOADED_MODELS=1 obrigatórios")
for e in erros:
    print("FALHA:", e)
sys.exit(1 if erros else 0)
PYTHON

echo "[5] entrypoint do worker-ai"
ENTRY=infra/entrypoints/worker-ai.sh
if [ -f "$ENTRY" ]; then
  ANTHROPIC_API_KEY=x CLAUDE_MODE=subscription sh "$ENTRY" true >/dev/null 2>&1 && falhar "aceitou ANTHROPIC_API_KEY no modo subscription"
  ANTHROPIC_API_KEY=x CLAUDE_MODE=api sh "$ENTRY" true >/dev/null 2>&1 || falhar "recusou ANTHROPIC_API_KEY no modo api"
  ANTHROPIC_API_KEY=x CLAUDE_MODE=" Subscription " sh "$ENTRY" true >/dev/null 2>&1 && falhar "modo com caixa/espaço contornou a guarda"
  ANTHROPIC_API_KEY= CLAUDE_MODE=invalido sh "$ENTRY" true >/dev/null 2>&1 && falhar "aceitou CLAUDE_MODE inválido"
  env -u ANTHROPIC_API_KEY CLAUDE_MODE=subscription sh "$ENTRY" true >/dev/null 2>&1 || falhar "recusou o modo subscription sem chave"
  ANTHROPIC_API_KEY= CLAUDE_MODE=subscription sh "$ENTRY" true >/dev/null 2>&1 || falhar "tratou chave vazia como definida"
else
  falhar "$ENTRY ausente"
fi

if [ "$falhas" -ne 0 ]; then echo "STATUS: FALHA ($falhas)"; exit 1; fi
echo "STATUS: OK"
