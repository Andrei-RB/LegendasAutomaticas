# Protocolo de construção de frontend

Aplica-se a toda tarefa que cria ou altera interface. A execução é automática: não depende de pedido na conversa.

## 1. Objetivo

Garantir que toda interface do Viraliza+ seja construída com o mesmo método, as mesmas skills e o mesmo padrão de qualidade, e que a evidência dessa qualidade acompanhe cada PR.

## 2. Escopo e detecção automática

A tarefa é de frontend quando atende a qualquer item:

| Gatilho | Mecanismo |
|---|---|
| Issue com a label `ui` | A sincronização de `docs/sprints/` acrescenta o bloco de `docs/sprints/bloco-ui.md` ao corpo da issue |
| Arquivo alterado em `frontend/` ou `pacotes/modelos-legenda/` | `CLAUDE.md`, seção 9.1; na máquina local, o hook `.claude/hooks/protocolo_frontend.sh` injeta o lembrete antes de qualquer `Edit` ou `Write` nesses caminhos |
| Texto da tarefa menciona tela, aba, modal, componente, layout, editor, galeria, prévia ou estado vazio | `CLAUDE.md`, seção 9.1 |

Quando o gatilho ocorre, o protocolo é aplicado sem consulta. Uma issue de interface sem a label `ui` deve receber a label antes do início.

## 3. Pré-requisitos

| Item | Condição | Se ausente |
|---|---|---|
| `PRODUCT.md` e `DESIGN.md` na raiz | Existem e refletem a direção atual | Interromper; executar `/impeccable init` ou `teach` e obter aprovação |
| Design system em `frontend/` | Tokens, componentes base e vitrine de desenvolvimento | Implementar o design system antes de qualquer tela nova |
| Skills disponíveis | Itens da seção 4 | Interromper e informar; as skills são locais e não versionadas |

## 4. Skills e referências

| Skill | Quando | Finalidade |
|---|---|---|
| `impeccable` (`shape`, `critique`, `polish`, `audit`, `detect`) | Toda tela | Planejar a UX, criticar, refinar e detectar anti-padrões |
| `pick-ui-library` | Antes de qualquer dependência de UI | Escolher o mínimo, verificar licença e manutenção |
| `emil-design-eng` | Interações, estados, movimento | Detalhes de acabamento; o que animar e o que não animar |
| `apple-design` | Movimento, gestos, tipografia, materiais | Movimento físico e interrompível; restrição visual |
| `vercel-react-best-practices` | Todo código React | Re-renderizações, divisão de código, tamanho do pacote |
| `web-design-guidelines` | Antes de revisar | Conformidade com as diretrizes de interface web |
| `modern-web-guidance` | HTML, CSS e JavaScript de navegador | Padrões atuais da plataforma web |
| `remotion-best-practices` | Prévia, editor de legenda, modelos | Mesmo pacote para prévia e render final |
| `design:ux-copy` | Textos de interface, erros, estados vazios | Microcopy direta, em PT-BR |
| `design:accessibility-review` | Antes do PR | Auditoria WCAG 2.2 AA |

Agentes: `explorador`, `escritor-testes`, `testador`, `revisor-ui`, `revisor-codigo`, `revisor-seguranca` e `verificador-conformidade`.

## 5. Sequência por tela

| Ordem | Etapa | Saída |
|---|---|---|
| 1 | Ler `PRODUCT.md`, `DESIGN.md` e a issue | Restrições e anti-padrões identificados |
| 2 | `/impeccable shape` | Plano de UX: hierarquia, fluxo, estados, mensagens, foco inicial, teclado |
| 3 | `escritor-testes` | Testes vermelhos (comportamento e acessibilidade) |
| 4 | Implementação com componentes e tokens do design system | Tela funcional |
| 5 | `emil-design-eng`, `apple-design`, `vercel-react-best-practices` (e `remotion-best-practices`, quando houver prévia) | Movimento, desempenho e acabamento |
| 6 | `/impeccable critique` e `/impeccable polish` | Achados tratados |
| 7 | Capturas Playwright em 1440 px e 390 px, nos temas escuro e claro | Imagens analisadas antes de declarar a tela pronta |
| 8 | `/verificar` | `STATUS: OK` |
| 9 | `revisor-ui`, `revisor-codigo` e `revisor-seguranca` em paralelo | Achados CRÍTICO e ALTO corrigidos |
| 10 | `/impeccable detect` ou `audit` e `web-design-guidelines` | Nenhum achado P0 ou P1 |
| 11 | `/conformidade` | Branch conforme `CLAUDE.md` seção 4 |

## 6. Padrão de qualidade

Referência: produtos finalistas em premiações de design de interface (por exemplo, Apple Design Awards e Awwwards). Os critérios abaixo traduzem essa referência em itens verificáveis. Todos são obrigatórios.

| Área | Critério |
|---|---|
| Acessibilidade | WCAG 2.2 AA; contraste 4,5:1 (texto) e 3:1 (bordas, ícones, foco); foco visível; operação completa por teclado; rótulo em todo campo; alvo de toque mínimo de 24 px (44 px no celular); status anunciado por região viva |
| Estados | Vazio, carregando (skeleton), erro, sucesso e, quando aplicável, parcial e sem conexão; ação principal clara no estado vazio |
| Desempenho | INP < 200 ms; LCP < 2,5 s; CLS < 0,1; nenhum quadro acima de 16 ms em interações; divisão de código por rota; fontes com carregamento controlado |
| Movimento | Apenas `transform` e `opacity`; durações e curvas vindas dos tokens; `prefers-reduced-motion` respeitado; nada bloqueia a interação; movimento só onde orienta a pessoa usuária |
| Responsivo | Desktop primeiro; verificado em 1440 px e 390 px; sem rolagem horizontal |
| Temas | Escuro como principal e claro completo, ambos com contraste aprovado |
| Consistência | Somente tokens e componentes do design system; sem cor, espaçamento ou raio literal |
| Conteúdo | Texto no catálogo i18n em PT-BR; mensagens diretas; sem dado, métrica ou depoimento inventado |
| Prévia | Prévia de legenda e render final usam o mesmo pacote Remotion |
| Segurança | Sem `dangerouslySetInnerHTML`; transcrição e texto de IA tratados como entrada não confiável; validação Zod nas fronteiras |
| Anti-padrões | Os listados em `PRODUCT.md` e `DESIGN.md` são proibidos |

## 7. Evidências no PR

- Capturas de antes e depois (1440 px e 390 px, escuro e claro).
- Métricas medidas (INP, LCP, CLS, acessibilidade) nas telas alteradas.
- Resultado de `vitest`, `playwright` e `tsc`.
- Bibliotecas novas com justificativa (`CLAUDE.md`, seção 13).
- Resultado do `detect` ou `audit` da `impeccable`.

## 8. Bloqueios

A tarefa não é concluída com qualquer um dos itens:

- teste falhando;
- achado CRÍTICO ou ALTO aberto nos revisores;
- achado P0 ou P1 da `impeccable`;
- tela sem captura analisada;
- estado ausente (vazio, carregando, erro, sucesso);
- dependência de UI sem justificativa.
