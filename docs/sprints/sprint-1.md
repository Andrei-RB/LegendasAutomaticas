<!-- epic: 🚀 S1 — Fatia vertical ponta a ponta | labels: epic, sprint-1 -->
**Objetivo:** fazer o fluxo inteiro funcionar de forma simples: vídeo → cortes → legenda → MP4 + SRT.

**Pronto quando:** um vídeo de 1 h vira N cortes 9:16 com legenda, baixáveis pela interface.

<!-- issue: [S1] Ingestão: upload retomável, ffprobe, proxy e áudio | labels: backend, sprint-1 -->
**Objetivo:** receber o vídeo e prepará-lo para análise.

- [ ] Upload retomável (tus ou em partes) para arquivos de 1 a 4 GB.
- [ ] Validação real com ffprobe (precisa ter stream de vídeo e áudio; até 1 h, configurável).
- [ ] Proxy em 480p com keyframe a cada 1 s, `audio.wav` 16k mono, picos da forma de onda e sprite de miniaturas.

**Aceite:** um arquivo falso é rejeitado; um vídeo real gera todos os artefatos.

<!-- issue: [S1] Transcrição com Whisper large-v3-turbo (GPU) | labels: backend, ia, sprint-1 -->
**Objetivo:** gerar a transcrição com tempo por palavra.

- [ ] `transcricao.json` com palavras (texto, início, fim, prob) e frases (IDs).
- [ ] Modelo, idioma (`pt`) e vocabulário configuráveis.
- [ ] VAD ligado.
- [ ] Liberar a VRAM depois de usar.

**Aceite:** 1 h de vídeo transcrita em menos de 8 min na RTX 4060 Ti.

<!-- issue: [S1] Candidatos alinhados a frases + nota de energia | labels: backend, cortes, sprint-1 -->
**Objetivo:** gerar janelas de corte usando só código.

- [ ] Janelas que começam e terminam em frase, com duração dentro do alvo ±20%.
- [ ] Nota simples: energia do áudio + densidade de fala.
- [ ] Remover sobreposições (IoU > 0,3) e ficar com o top `max(4N, 30)`.
- [ ] 3 variantes de início e 3 de fim por candidato.

**Aceite:** nenhum candidato corta palavra ou começa no meio de uma frase (teste).

<!-- issue: [S1] Triagem com Qwen local (Ollama) | labels: ia, cortes, sprint-1 -->
**Objetivo:** dar nota aos candidatos com IA local.

- [ ] Rubrica de 0 a 10 (gancho, contexto, desfecho, emoção, clareza) em JSON schema.
- [ ] A resposta traz só o `candidato_id` e uma citação literal.
- [ ] Validar o JSON; se vier inválido, descartar.
- [ ] Os N melhores viram cortes para revisão.

**Aceite:** um ID inventado pela IA é rejeitado (teste com mock).

<!-- issue: [S1] Redesenho da interface: marca, design system e telas-base | labels: frontend, sprint-1, ui -->
**1. Objetivo:** substituir a interface base por uma identidade e um design system próprios, e entregar login, Biblioteca, Painel e Configurações no padrão de qualidade do protocolo de frontend, antes das telas de fluxo.

**2. Contexto:**
- `docs/protocolo-frontend.md`, `PRODUCT.md`, `DESIGN.md` e `.impeccable/design.json`.
- Estado atual: login funcional; Biblioteca, Painel e Configurações são marcadores de posição.
- Perfil de medição: CPU 6x mais lenta e rede Fast 3G (cerca de 1,6 Mbps, 150 ms de RTT), emulados no Chromium.
- Primitivos de acessibilidade: React Aria Components, carregados por rota e somente os usados; a rota de login não usa biblioteca. A escolha é confirmada com `pick-ui-library` e com a medição de bytes na Fase 2; a alternativa é Radix Primitives.
- Tipografia: fonte variável com licença OFL, subconjunto WOFF2 hospedado localmente.

| Métrica (sob o perfil acima) | Orçamento |
|---|---|
| LCP / INP / CLS | < 2,5 s / < 200 ms / < 0,1 |
| JS inicial da rota de login (comprimido) | ≤ 90 KB |
| JS de qualquer rota (comprimido) | ≤ 170 KB |
| CSS crítico | ≤ 20 KB |
| Fontes | ≤ 30 KB por pacote |

**3. Dependências:** #17 (frontend base) e #18 (CI).

**4. Tarefas (uma fase por PR; a fase seguinte começa após validação da anterior):**
- [ ] Fase 1, direção visual: marca (nome estilizado, logotipo em SVG, peso de destaque), tipografia e densidade; atualizar `PRODUCT.md` e `DESIGN.md`.
- [ ] Fase 2, design system: tokens de cor, tipografia, espaço, raio e movimento; componentes base com estados completos; vitrine de desenvolvimento fora do pacote de produção; teste de orçamento de bytes por rota.
- [ ] Fase 3, login e marca: tela com expressão de marca, formulário acessível, erro e carregamento.
- [ ] Fase 4, layout e telas: estrutura de navegação, Biblioteca, Painel e Configurações com estados vazio, carregando, erro, sucesso, parcial e sem conexão; 390 px e 1440 px.
- [ ] Fase 5, movimento: transições com `transform` e `opacity`, `prefers-reduced-motion`, nenhum quadro acima de 16 ms.
- [ ] Fase 6, auditoria: `detect` ou `audit` da `impeccable`, `design:accessibility-review`, medição sob o perfil 6x/3G e capturas analisadas.

**5. Fora de escopo:** telas de Enviar, Análise, Galeria e Editor (issue "API e telas"); página de apresentação; service worker e uso offline; idiomas além de PT-BR.

**6. Testes exigidos:** acessibilidade automatizada por componente (axe); navegação completa por teclado nas telas; orçamento de bytes por rota; contraste dos tokens nos dois temas; Playwright com capturas em 1440 px e 390 px, nos temas escuro e claro.

**7. Aceite:**
- `cd frontend && npm run test && npx playwright test` aprovados.
- Medição sob o perfil 6x/3G dentro dos orçamentos da seção 2.
- `detect` ou `audit` sem achado P0 ou P1; revisores sem achado CRÍTICO ou ALTO.
- PR com capturas, métricas e roteiro "O que ver".

<!-- issue: [S1] Medição de desempenho no CI (Lighthouse CI, perfil 6x/3G) | labels: testes, infra, frontend, sprint-1 -->
**1. Objetivo:** medir LCP, INP, CLS e tamanho de pacote a cada PR sob o perfil de celular modesto e rede lenta.

**2. Contexto:**
- Orçamentos na issue "Redesenho da interface".
- Perfil: CPU 6x mais lenta e rede Fast 3G, emulados no Chromium.
- O job começa informativo; torna-se obrigatório na `main` após uma linha de base estável.

**3. Dependências:** #18 e a Fase 2 da issue "Redesenho da interface".

**4. Tarefas:**
- [ ] Job `desempenho` com Lighthouse CI contra a pilha de CI.
- [ ] Configuração versionada do perfil e dos orçamentos.
- [ ] Relatório anexado ao PR.
- [ ] Linha de base registrada em `docs/`.

**5. Fora de escopo:** monitoramento em produção.

**6. Testes exigidos:** um PR de teste que ultrapassa o orçamento de bytes deixa o job vermelho; o PR é descartado sem mesclar.

**7. Aceite:**
- `gh run list --workflow ci.yml --limit 3` mostra o job `desempenho`.
- Após a linha de base, o job consta na proteção da `main`.

<!-- issue: [S1] Varreduras de segurança no CI (dependências, imagens, segredos, código) | labels: infra, testes, sprint-1 -->
**1. Objetivo:** detectar vulnerabilidades, segredos e más configurações em cada PR, com ferramentas gratuitas.

**2. Contexto:**
- Alvo: OWASP ASVS e Top 10, alinhamento NIST CSF.
- O repositório é público: o CodeQL é gratuito.
- Já existem `pip-audit` e o Dependabot.

**3. Dependências:** #18.

**4. Tarefas:**
- [ ] Trivy sobre o sistema de arquivos e as imagens do compose.
- [ ] gitleaks sobre o histórico e o diff.
- [ ] Semgrep com regras de Python, TypeScript e Docker.
- [ ] CodeQL para Python e JavaScript/TypeScript.
- [ ] hadolint nos Dockerfiles.
- [ ] OSV-Scanner para `npm` e `pip`.
- [ ] Actions fixadas por SHA, com atualização pelo Dependabot.
- [ ] SBOM (Syft) anexado à execução.
- [ ] Achados de severidade alta bloqueiam o PR; exceções documentadas em arquivo versionado.

**5. Fora de escopo:** varredura dinâmica (issue de OWASP ZAP na S7).

**6. Testes exigidos:** um segredo falso e uma dependência vulnerável em PR de teste deixam o job vermelho; o PR é descartado sem mesclar.

**7. Aceite:**
- Jobs de segurança verdes na `main`.
- Os jobs constam na proteção da `main`.

<!-- issue: [S1] API e telas: enviar, análise, galeria, editor mínimo | labels: backend, frontend, sprint-1, ui -->
**Objetivo:** permitir usar o fluxo pela interface.

**Dependência:** design system aprovado (issue "Redesenho da interface", Fase 2).

- [ ] Telas: Enviar (perfil, duração, N) e Análise (etapas ao vivo + notificação do navegador).
- [ ] Galeria com nota e motivo.
- [ ] Editor mínimo: Player Remotion + alças de início e fim alinhadas à palavra (o servidor revalida).

**Aceite:** dá para ajustar o início de um corte e o ajuste fica salvo.

<!-- issue: [S1] Legenda e render básicos (Remotion + ffmpeg) | labels: legendas, render, sprint-1 -->
**Objetivo:** gerar o primeiro vídeo final com legenda.

- [ ] `DocumentoLegenda` básico (palavras do corte).
- [ ] Pacote `pacotes/modelos-legenda` com 1 modelo (Bold), modo frase curta.
- [ ] Serviço `render`: camada de legenda com alfa.
- [ ] ffmpeg: recorte central 9:16 + sobreposição da camada + x264 CRF 17 + `loudnorm`.
- [ ] Exportar o SRT (frase curta).

**Aceite:** o MP4 toca no celular e o SRT importa sincronizado no CapCut.
