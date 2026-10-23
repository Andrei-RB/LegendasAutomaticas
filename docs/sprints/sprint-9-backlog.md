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

<!-- issue: [Backlog] Simulador de post (mockup TikTok/Reels) | labels: backlog, frontend, ui -->
- [ ] Mostrar o vídeo com o texto num mockup do app.

<!-- issue: [Backlog] Segredos em arquivo (secrets) em vez de variáveis de ambiente | labels: backlog, seguranca, infra -->
- [ ] Montar os segredos em `/run/secrets` e lê-los no backend (`secrets_dir`), sem variáveis de ambiente nos contêineres.
- [ ] Passar a subprocessos (ffmpeg, yt-dlp, `claude -p`) um ambiente mínimo.
- [ ] Declarar `REDIS_URL` como `SecretStr` (hoje a senha aparece em `repr(settings)`).

<!-- issue: [Backlog] Cadeia de suprimentos das imagens e dependências | labels: backlog, seguranca, infra -->
- [ ] Fixar imagens por digest (`tag@sha256`).
- [ ] Gerar lock com hashes e instalar com `--require-hashes`; auditar o lock no CI.
- [ ] Separar o volume de modelos (escrita só no `worker-gpu`) dos volumes de uploads e saídas.

<!-- issue: [Backlog] Row Level Security como segunda camada de isolamento | labels: backlog, seguranca, backend -->
- [ ] Avaliar RLS por `user_id` (`SET LOCAL app.user_id` por transação) sobre o papel `viraliza_app`.
- [ ] Medir o custo em consultas do pipeline antes de adotar.

<!-- issue: [Backlog] Coletores de métricas por API (TikTok, YouTube, Instagram) | labels: backlog, backend -->
- [ ] Implementar `ColetorMetricas` para as APIs das plataformas, com autorização do próprio usuário.
- [ ] Manter `ColetorManual` como reserva.

<!-- issue: [Backlog] Proxy de saída com lista de domínios permitidos para os workers de IA | labels: backlog, seguranca, infra -->
- [ ] Limitar a saída de rede dos workers de IA aos domínios dos provedores autorizados.
- [ ] Testar o bloqueio de domínio fora da lista.

<!-- issue: [Backlog] Serviço worker-agy dedicado, sem volume dados e sem segredos | labels: backlog, seguranca, infra -->
- [ ] Isolar o agy em serviço próprio, com fila `ai_agy` e volume `clipes_ia`, sem `dados` e sem segredos (plano B2 do spike agy).
