#!/usr/bin/env bash
# Funções compartilhadas pelos hooks e pela Action verificar-autoria.

RAIZ="$(git rev-parse --show-toplevel)"
LISTA="$RAIZ/.githooks/autores-permitidos"

# Marcadores de atribuição de IA (em qualquer linha da mensagem).
MARCADORES_IA='claude-session:|generated with|gerado (com|por)|🤖|noreply@anthropic\.com|co-authored-by:.*(claude|copilot|chatgpt|openai|gemini|anthropic|cursor|codeium|tabnine)'

# Retorna 0 se a identidade "Nome <email>" (ou só nome/e-mail) está na lista.
identidade_permitida() {
  local ident="$1" nome email item
  nome="$(printf '%s' "$ident" | sed -E 's/[[:space:]]*<.*//' | xargs)"
  email="$(printf '%s' "$ident" | sed -nE 's/.*<([^>]*)>.*/\1/p' | xargs)"
  while IFS= read -r item; do
    item="$(printf '%s' "$item" | xargs)"
    [[ -z "$item" || "$item" == \#* ]] && continue
    shopt -s nocasematch
    if [[ -n "$email" && "$email" == "$item" ]] || [[ -n "$nome" && "$nome" == "$item" ]]; then
      shopt -u nocasematch; return 0
    fi
    shopt -u nocasematch
  done < "$LISTA"
  return 1
}

# Verifica uma mensagem de commit (texto em $1). Imprime erros e retorna 1 se inválida.
verificar_mensagem() {
  local msg="$1" erro=0 linha coautor
  if printf '%s\n' "$msg" | grep -v '^#' | grep -qiE "$MARCADORES_IA"; then
    echo "✖ A mensagem contém atribuição de IA:" >&2
    printf '%s\n' "$msg" | grep -v '^#' | grep -iE "$MARCADORES_IA" | sed 's/^/    /' >&2
    erro=1
  fi
  while IFS= read -r linha; do
    coautor="$(printf '%s' "$linha" | sed -E 's/^[Cc][Oo]-[Aa][Uu][Tt][Hh][Oo][Rr][Ee][Dd]-[Bb][Yy]:[[:space:]]*//')"
    if ! identidade_permitida "$coautor"; then
      echo "✖ Coautor não autorizado: $coautor" >&2
      erro=1
    fi
  done < <(printf '%s\n' "$msg" | grep -v '^#' | grep -iE '^co-authored-by:')
  return $erro
}
