#!/bin/sh
# Impede cobrança na API quando o modo é assinatura: a chave da API não pode coexistir.
set -eu

modo=$(printf '%s' "${CLAUDE_MODE:-subscription}" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')

case "$modo" in
  subscription|api|off) ;;
  *)
    echo "ERRO: CLAUDE_MODE inválido. Use subscription, api ou off." >&2
    exit 1
    ;;
esac

if [ "$modo" = "subscription" ] && [ -n "${ANTHROPIC_API_KEY:-}" ]; then
  echo "ERRO: ANTHROPIC_API_KEY definida com CLAUDE_MODE=subscription. Remova a chave ou use CLAUDE_MODE=api." >&2
  exit 1
fi

if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  unset ANTHROPIC_API_KEY
fi

export CLAUDE_MODE="$modo"
exec "$@"
