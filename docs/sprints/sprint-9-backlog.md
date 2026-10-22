<!-- epic: 💡 Backlog — ideias para depois | labels: epic, backlog -->
Ideias boas que ficaram fora da v2. Avaliar depois da S7.

<!-- issue: [Backlog] Remover silêncios e vícios de fala com remapeamento da legenda | labels: backlog, render -->
- [ ] Cortar pausas e "é..., tipo, né" usando os tempos das palavras.
- [ ] Remapear a legenda para a nova linha do tempo.

<!-- issue: [Backlog] Áudio: redução de ruído e música com ducking | labels: backlog, render -->
- [ ] Redução de ruído (`afftdn` ou DeepFilterNet).
- [ ] Música de fundo que abaixa sozinha quando alguém fala.

<!-- issue: [Backlog] Zoom automático em momentos de impacto | labels: backlog, render -->
- [ ] Punch-in de 1,12–1,2× nos momentos-chave da legenda.

<!-- issue: [Backlog] Tradução de legendas (EN/ES) | labels: backlog, legendas, ia -->
- [ ] Traduzir por frase, preservando os tempos.

<!-- issue: [Backlog] Sugestão de thumbnail | labels: backlog, ia -->
- [ ] Frames candidatos → o juiz multimodal escolhe → PNG com texto.

<!-- issue: [Backlog] Simulador de post (mockup TikTok/Reels) | labels: backlog, frontend -->
- [ ] Mostrar o vídeo com o texto num mockup do app.

<!-- issue: [Backlog] Segredos em arquivo (secrets) em vez de variáveis de ambiente | labels: backlog, seguranca, infra -->
- [ ] Montar os segredos em `/run/secrets` e lê-los no backend (`secrets_dir`), sem variáveis de ambiente nos contêineres.
- [ ] Passar a subprocessos (ffmpeg, yt-dlp, `claude -p`) um ambiente mínimo.

<!-- issue: [Backlog] Cadeia de suprimentos das imagens e dependências | labels: backlog, seguranca, infra -->
- [ ] Fixar imagens por digest (`tag@sha256`).
- [ ] Gerar lock com hashes e instalar com `--require-hashes`; auditar o lock no CI.
- [ ] Separar o volume de modelos (escrita só no `worker-gpu`) dos volumes de uploads e saídas.
