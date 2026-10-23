**Construção de frontend (obrigatória).** Esta tarefa cria ou altera interface. Seguir `docs/protocolo-frontend.md` do início ao fim, sem aguardar pedido. Pré-requisitos: `PRODUCT.md`, `DESIGN.md` e o design system do `frontend/`; se faltarem, interromper e resolver antes de qualquer tela.

**Etapas de interface:**
- [ ] Ler `PRODUCT.md`, `DESIGN.md` e o protocolo; respeitar os anti-padrões listados.
- [ ] Planejar cada tela com `/impeccable shape` (hierarquia, fluxo, estados, teclado, foco).
- [ ] Implementar só com componentes e tokens do design system; biblioteca nova passa por `pick-ui-library` e é justificada no PR.
- [ ] Aplicar `emil-design-eng`, `apple-design` e `vercel-react-best-practices` (e `remotion-best-practices` quando houver prévia ou legenda).
- [ ] Executar `/impeccable critique` e `/impeccable polish`; revisar com `web-design-guidelines`.
- [ ] Capturar telas com Playwright em 1440 px e 390 px, nos temas escuro e claro, e analisá-las antes de declarar a tela pronta.
- [ ] Cobrir comportamento e acessibilidade com vitest e o fluxo com Playwright, incluindo operação só por teclado.
- [ ] Revisar com `revisor-ui`, `revisor-codigo` e `revisor-seguranca`; corrigir todo achado CRÍTICO e ALTO.
- [ ] Rodar `/impeccable detect` ou `audit` sem achado P0 ou P1.

**Padrão de qualidade (todos obrigatórios):**
- WCAG 2.2 AA, foco visível e operação completa por teclado.
- Estados vazio, carregando, erro e sucesso em toda tela.
- INP < 200 ms, LCP < 2,5 s, CLS < 0,1; movimento só com `transform` e `opacity`, respeitando `prefers-reduced-motion`.
- Escuro como tema principal e claro completo, ambos com contraste aprovado.
- Somente tokens e componentes do design system; textos no catálogo i18n em PT-BR.
- Sem dado, métrica ou depoimento inventado; transcrição e texto de IA tratados como entrada não confiável.

**Evidências no PR:** capturas de antes e depois, métricas medidas, resultado de `vitest`, `playwright` e `tsc`, e justificativa das bibliotecas novas.
