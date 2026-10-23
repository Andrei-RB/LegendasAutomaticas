<!-- epic: 📣 S6 — Postagens, link do YouTube e re-gerar cortes | labels: epic, sprint-6 -->
**Objetivo:** entregar o texto de postagem pronto e dar controle total sobre os cortes.

**Pronto quando:** os textos passam na validação e as hashtags têm no máximo 24 h.

<!-- issue: [S6] Textos de postagem das 4 plataformas (Claude) | labels: ia, backend, sprint-6 -->
**Objetivo:** gerar o texto de cada plataforma.

- [ ] TikTok: legenda + hashtags.
- [ ] Shorts: título + descrição + tags.
- [ ] Reels: legenda + hashtags.
- [ ] YouTube longo: título, descrição, tags e capítulos (capítulos por IDs de frase e cena, nunca tempo inventado).
- [ ] Limites de caracteres conferidos no código.
- [ ] Reserva: Haiku (API) → Qwen.

**Aceite:** os textos respeitam os limites de cada plataforma.

<!-- issue: [S6] Hashtags em alta (Claude + busca web) com cache | labels: ia, sprint-6 -->
**Objetivo:** usar hashtags realmente em alta.

- [ ] `claude -p` com WebSearch por nicho.
- [ ] Cache de 24 h em `cache_hashtags`.
- [ ] Juntar com a lista fixa do usuário.
- [ ] Temas em alta por nicho: a triagem devolve `temas_ids`; o código confirma a palavra-chave no texto do corte.
- [ ] Temas têm peso 0,5 e ficam fora do consenso dos juízes.

**Aceite:** a segunda análise do mesmo nicho não chama o Claude.

<!-- issue: [S6] Tela de postagens (abas por plataforma) | labels: frontend, sprint-6 -->
**Objetivo:** copiar o texto pronto rapidamente.

- [ ] Abas editáveis, com contador e limite de caracteres.
- [ ] Hashtags como etiquetas removíveis.
- [ ] Botões "copiar" e "regerar com outro tom".

**Aceite:** o botão copiar funciona também no celular.

<!-- issue: [S6] Entrada por link YouTube/Twitch (yt-dlp) | labels: backend, frontend, sprint-6 -->
**Objetivo:** analisar um vídeo a partir de um link.

- [ ] Baixar com yt-dlp, com aviso de direitos autorais aceito e registrado.
- [ ] Recurso atrás de uma flag (desligado por padrão em modo SaaS).

**Aceite:** um link de vídeo próprio é processado como upload.

<!-- issue: [S6] Gerar mais, buscar por tema e momento favorito | labels: cortes, backend, frontend, sprint-6 -->
**Objetivo:** dar alternativas quando os cortes não agradam.

- [ ] "Gerar mais": próximos candidatos, sem repetir os já vistos.
- [ ] "Buscar por tema": o Qwen procura nas frases e o código monta as janelas.
- [ ] "Momento favorito": um clique gera janelas em volta do instante, que passam pelo mesmo funil.

**Aceite:** nenhuma das três opções reprocessa o vídeo.

<!-- issue: [S6] Exportação em lote | labels: render, frontend, sprint-6 -->
**Objetivo:** exportar vários cortes de uma vez.

- [ ] Selecionar vários cortes, aplicar o mesmo modelo e enfileirar.
- [ ] Mostrar o progresso de cada um.

**Aceite:** 5 cortes exportados em fila, sem travar a interface.

<!-- issue: [S6] Sugestões a partir de quase-aprovados | labels: ia, cortes, sprint-6 -->
**Objetivo:** transformar cortes quase aprovados em opções de ajuste.

- [ ] Quase-aprovado: nota a até `IA_QUASE_MARGEM` (padrão 1,0) do limiar.
- [ ] O código gera opções de ajuste por ID: variantes, deslocamento de 1 a 3 frases e limites de cena.
- [ ] O editor escolhe um `ajuste_id`; o sistema cria um candidato com `origem=ajuste` e `candidato_pai_id`, exibido em "Sugestões".
- [ ] Os validadores rodam de novo sobre o candidato criado.

**Aceite:** o editor escolhe apenas `ajuste_id`; nenhum tempo vem de LLM e os validadores passam de novo.

<!-- issue: [S6] Publicações e métricas manuais | labels: backend, frontend, sprint-6 -->
**Objetivo:** registrar publicações e métricas digitadas para medir a relação com a nota.

- [ ] Tabelas `publicacoes` e `metricas_publicacao`, com `user_id` e consultas filtradas por usuário.
- [ ] `Protocol ColetorMetricas` com a implementação `ColetorManual`; coletores por API ficam no backlog.
- [ ] Validação de faixas: valores não negativos e retenção entre 0 e 100%.
- [ ] Tela para digitar as métricas de cada publicação.

**Aceite:** valores fora da faixa são rejeitados pela API e pela interface.
