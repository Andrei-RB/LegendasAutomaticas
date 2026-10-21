# Ativa os githooks do projeto no Windows (rode uma vez por clone).
# Os hooks são bash: o Git for Windows já inclui o bash necessário.
Set-Location (git rev-parse --show-toplevel)
git config core.hooksPath .githooks
Write-Host "Hooks ativos (.githooks). Autor configurado: $(git config user.name) <$(git config user.email)>"
