#!/usr/bin/env bash
# Verifica autor, coautores e atribuição de IA em um intervalo de commits.
# Uso: .githooks/verificar-intervalo.sh <base>..<topo>
set -u
source "$(git rev-parse --show-toplevel)/.githooks/_comum.sh"
intervalo="$1"; falhas=0
for sha in $(git rev-list --no-merges "$intervalo"); do
  autor="$(git log -1 --format='%an <%ae>' "$sha")"
  committer="$(git log -1 --format='%cn <%ce>' "$sha")"
  problemas=""
  identidade_permitida "$autor" || problemas+=" autor=$autor;"
  # Commits feitos pela interface web do GitHub têm committer "GitHub <noreply@github.com>".
  [[ "$committer" == "GitHub <noreply@github.com>" ]] || identidade_permitida "$committer" || problemas+=" committer=$committer;"
  verificar_mensagem "$(git log -1 --format=%B "$sha")" 2>/tmp/msg_erros || problemas+=" $(tr '\n' ' ' </tmp/msg_erros)"
  if [[ -n "$problemas" ]]; then
    echo "✖ ${sha:0:7}:$problemas"; falhas=$((falhas + 1))
  fi
done
if [[ $falhas -gt 0 ]]; then
  echo "$falhas commit(s) violam a regra de autoria (CLAUDE.md, seção 4.1)."; exit 1
fi
echo "✔ Autoria ok em $intervalo"
