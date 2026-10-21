#!/usr/bin/env bash
# Ativa os githooks do projeto (rode uma vez por clone).
set -e
cd "$(git rev-parse --show-toplevel)"
git config core.hooksPath .githooks
chmod +x .githooks/commit-msg .githooks/pre-commit .githooks/*.sh
echo "✔ Hooks ativos (.githooks). Autor configurado: $(git config user.name) <$(git config user.email)>"
