# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Criadores de conteúdo de 18 a 39 anos que revisam muitos cortes por dia. Trabalham em máquina própria com GPU NVIDIA, a partir de vídeos longos (até 1 h) de YouTube, Twitch ou arquivo local. A tarefa central é aprovar, ajustar ou descartar cortes sugeridos e publicar o resultado em vários canais.

## Product Purpose

Receber um vídeo longo e entregar cortes curtos em 9:16, selecionados e validados automaticamente, com legendas estilizadas (MP4 e SRT) e textos de publicação para TikTok, YouTube Shorts, Instagram Reels e YouTube.

Sucesso: a pessoa gasta o tempo em decidir, não em procurar; a análise de 1 h de vídeo termina em 20–35 min e a revisão manual cobre apenas o que o sistema não consegue validar.

## Positioning

- Execução local em Docker: o vídeo original não sai da máquina; apenas trechos em 360p de candidatos selecionados podem ir a provedores externos, e o sistema funciona com todos eles desativados.
- Tempos de corte e de legenda medidos por sinais (ASR, alinhamento forçado, cenas, áudio), nunca gerados por modelo de linguagem.
- Aprovação por consenso de dois avaliadores de famílias distintas mais validadores determinísticos.
- A prévia da legenda e o vídeo final usam o mesmo pacote de renderização.

## Operating Context

- Uso diário e repetitivo, em sessões de revisão de muitos cortes seguidos; teclado e resposta imediata pesam mais que efeito visual.
- Máquina única com GPU de 8 GB e 16 GB de RAM; tarefas pesadas rodam em fila, e a interface acompanha o andamento por eventos do servidor.
- Isolamento por `user_id` desde a origem, para múltiplos usuários no futuro.
- Interface em PT-BR.

## Capabilities and Constraints

- Etapas do fluxo: ingestão, sinais, linha do tempo, candidatos, triagem, juiz, editor, consenso, revisão manual, enquadramento, legendas, renderização e postagens.
- Tema escuro por padrão, com alternância para claro.
- Telas hoje existentes: login, biblioteca, painel e configurações. Demais telas (revisão de cortes, editor de legenda) ainda não existem.
- Decisões de produto em aberto: nome e identidade visual de marca, página de apresentação (landing) e idiomas além de PT-BR.

## Brand Commitments

- Nome do produto: Viraliza+.
- A marca ganha expressão de impacto apenas no login e na landing; o restante da aplicação prioriza fluidez e clareza.

## Evidence on Hand

- Interface funcional de login e navegação em `frontend/` (tokens em `frontend/src/estilos.css`).
- Não há depoimentos, clientes, métricas de uso, logotipo ou material de marca. Nenhum deve ser inventado.

## Product Principles

1. Fluidez antes de efeito: a interface responde de imediato e nada atrasa o trabalho de revisão.
2. Clareza do estado: a pessoa sempre sabe o que o sistema fez, o que falta e o que depende dela.
3. O que o sistema mede é mostrado como medido; o que um modelo sugeriu é mostrado como sugestão.
4. Decisão rápida por teclado: a ação frequente tem atalho e não exige o mouse.
5. Funcionar sem serviços externos: nenhuma tela depende de provedor de IA disponível.

## Accessibility & Inclusion

WCAG 2.2 AA: contraste, foco visível, operação completa por teclado, rótulos em todos os campos e respeito a `prefers-reduced-motion`. Textos em PT-BR.
