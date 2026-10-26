---
name: Viraliza+
description: Ferramenta de trabalho densa e silenciosa para revisar cortes de vídeo, com um único acento laranja.
colors:
  primary: "oklch(0.72 0.19 40)"
  primary-claro: "oklch(0.56 0.21 36)"
  on-primary: "oklch(0.17 0.01 40)"
  on-primary-claro: "oklch(0.99 0 0)"
  fundo: "oklch(0.16 0.006 60)"
  fundo-claro: "oklch(0.985 0.002 80)"
  superficie: "oklch(0.2 0.007 60)"
  superficie-clara: "oklch(1 0 0)"
  superficie-suave: "oklch(0.24 0.008 60)"
  superficie-suave-clara: "oklch(0.955 0.004 80)"
  texto: "oklch(0.96 0.004 80)"
  texto-claro: "oklch(0.2 0.01 60)"
  texto-suave: "oklch(0.72 0.01 70)"
  texto-suave-claro: "oklch(0.45 0.01 60)"
  divisor: "oklch(0.3 0.008 60)"
  divisor-claro: "oklch(0.89 0.006 80)"
  borda-campo: "oklch(0.54 0.01 60)"
  borda-campo-clara: "oklch(0.62 0.008 80)"
  erro: "oklch(0.7 0.19 25)"
  erro-claro: "oklch(0.5 0.2 27)"
typography:
  titulo:
    fontFamily: "ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 600
    lineHeight: 1.33
    letterSpacing: "-0.025em"
  marca:
    fontFamily: "ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 600
    lineHeight: 1.56
    letterSpacing: "-0.025em"
  corpo:
    fontFamily: "ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.43
  rotulo:
    fontFamily: "ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 500
    lineHeight: 1.43
rounded:
  md: "0.5rem"
  lg: "calc(0.5rem + 2px)"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
components:
  botao-primario:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    rounded: "{rounded.md}"
    typography: "{typography.rotulo}"
    height: "40px"
    padding: "0 16px"
  botao-contorno:
    backgroundColor: "transparent"
    textColor: "{colors.texto}"
    rounded: "{rounded.md}"
    typography: "{typography.rotulo}"
    height: "40px"
    padding: "0 16px"
  botao-fantasma:
    backgroundColor: "transparent"
    textColor: "{colors.texto}"
    rounded: "{rounded.md}"
    size: "40px"
  campo:
    backgroundColor: "transparent"
    textColor: "{colors.texto}"
    rounded: "{rounded.md}"
    typography: "{typography.corpo}"
    height: "40px"
    padding: "0 12px"
  cartao:
    backgroundColor: "{colors.superficie}"
    textColor: "{colors.texto}"
    rounded: "{rounded.lg}"
    padding: "24px"
  item-menu-ativo:
    backgroundColor: "{colors.superficie-suave}"
    textColor: "{colors.primary}"
    rounded: "{rounded.md}"
    typography: "{typography.rotulo}"
    padding: "8px 12px"
---

# Sistema de design: Viraliza+

Os valores acima descrevem a implementação existente em `frontend/src/estilos.css` e nos componentes de `frontend/src/componentes/`. Sufixo `-claro` indica o tema claro; os demais valem para o tema escuro, que é o padrão.

## 1. Visão geral

**Norte criativo: "A Mesa de Edição"**

A aplicação é uma bancada de trabalho: superfícies escuras e neutras, texto de alto contraste e um único acento laranja que marca apenas o que está ativo ou é a próxima ação. A interface recua para que o vídeo e a transcrição ocupem o primeiro plano. Prioridade: fluidez e clareza, para quem revisa muitos cortes por dia.

Referências de comportamento, confirmadas pela direção do produto: a resposta instantânea, a barra lateral densa e silenciosa e os atalhos de teclado de uma ferramenta de gestão de tarefas; o acento que se destaca sobre o fundo escuro sem cansar, como em um lançador de comandos; a convivência de transcrição e vídeo na mesma tela, como em um editor de vídeo por texto. A marca (login e página de apresentação) pode ser mais expressiva, com tipografia de destaque e transições entre seções, desde que o movimento tenha propósito. Esse trecho de marca ainda não foi implementado.

Rejeições confirmadas: cartão centralizado genérico, gradiente roxo, ícones decorativos sem função e animações que atrasem o trabalho.

**Características principais:**
- Tema escuro por padrão; tema claro equivalente, com os mesmos papéis de cor.
- Neutros levemente quentes (matiz 60–80) e um acento laranja; nenhuma segunda cor de destaque.
- Superfícies planas, separadas por filete de 1 px, sem sombra.
- Tipografia do sistema; hierarquia por peso e tamanho, não por fonte.
- Densidade média: alvos de 40 px, texto de 14 px.

## 2. Cores

Neutros quentes com um acento laranja de baixa frequência. Todos os valores em `oklch`, a fonte única de verdade.

### 2.1 Primária
- **Laranja de Ação** (`oklch(0.72 0.19 40)` no escuro; `oklch(0.56 0.21 36)` no claro): fundo do botão primário, item de menu ativo, marca, anel de foco. Contraste do texto sobre ele: 4,5:1 ou mais nos dois temas.

### 2.2 Neutras
- **Fundo Grafite** (`oklch(0.16 0.006 60)`) / **Fundo Papel** (`oklch(0.985 0.002 80)`): fundo da página.
- **Superfície** (`oklch(0.2 0.007 60)` / `oklch(1 0 0)`): barra lateral e cartões.
- **Superfície Suave** (`oklch(0.24 0.008 60)` / `oklch(0.955 0.004 80)`): item ativo e passagem do cursor.
- **Texto** (`oklch(0.96 0.004 80)` / `oklch(0.2 0.01 60)`) e **Texto Suave** (`oklch(0.72 0.01 70)` / `oklch(0.45 0.01 60)`): texto principal e secundário.
- **Divisor** (`oklch(0.3 0.008 60)` / `oklch(0.89 0.006 80)`): bordas de cartão e barra lateral; decorativo, sem exigência de contraste.
- **Borda de Campo** (`oklch(0.54 0.01 60)` / `oklch(0.62 0.008 80)`): contorno de campos e botão de contorno; contraste de 3:1 ou mais contra fundo e superfície, garantido por teste.
- **Erro** (`oklch(0.7 0.19 25)` / `oklch(0.5 0.2 27)`): mensagens e campo inválido.

### 2.3 Regras nomeadas
**A Regra de Uma Voz.** O laranja marca apenas o item ativo, a ação primária da tela e o foco. Se mais de um elemento por região competir por ele, nenhum se destaca.

**A Regra do Contraste.** Todo texto atinge 4,5:1 e todo contorno de componente interativo atinge 3:1. O teste `src/tema/contraste.test.ts` falha ao violar.

## 3. Tipografia

**Fonte de interface:** pilha do sistema (`ui-sans-serif`, `system-ui`, Segoe UI, Roboto, Arial). Sem fonte própria hoje.

**Caráter:** neutra e nativa; a identidade vem do peso e do espaçamento, não da família. A fonte de destaque da marca (login e página de apresentação) está em aberto.

### 3.1 Hierarquia
- **Título** (600, 1,5 rem, 1,33, tracking −0,025 em): título de página e do formulário.
- **Marca** (600, 1,125 rem, 1,56, tracking −0,025 em, cor de acento): nome do produto na barra lateral.
- **Corpo** (400, 0,875 rem, 1,43): conteúdo e mensagens.
- **Rótulo** (500, 0,875 rem, 1,43): rótulos de campo, botões e itens de menu.

### 3.2 Regras nomeadas
**A Regra do Tamanho Único.** Texto de interface fica em 14 px; a escala só sobe para título e marca.

## 4. Layout

Aplicação com barra lateral fixa de 15 rem e área de conteúdo de até 72 rem (`max-w-6xl`) com margem de 32 px; abaixo de `md` a barra vira faixa superior. Espaçamento em múltiplos de 4 px, ritmo de 16 px entre campos. Altura mínima `100dvh`. A tela de trabalho futura deve manter transcrição e vídeo lado a lado sem trocar de contexto.

## 5. Elevação e profundidade

Plano por padrão: a profundidade vem de camadas tonais (fundo, superfície, superfície suave) e de filetes de 1 px, sem nenhuma sombra. Sombra só seria admitida em sobreposições flutuantes (menus, diálogos), que ainda não existem.

### 5.1 Regras nomeadas
**A Regra do Plano.** Superfícies em repouso não têm sombra, borda dupla nem cartão dentro de cartão.

## 6. Formas

Cantos suaves e consistentes: 0,5 rem em botões, campos e itens de menu; 10 px nos cartões. Bordas de 1 px. Sem formas decorativas.

## 7. Componentes

Sóbrios e previsíveis; cada estado é distinguível sem depender só de cor.

### 7.1 Botões
- **Forma:** cantos de 0,5 rem, altura de 40 px, padding horizontal de 16 px.
- **Primário:** fundo laranja, texto escuro (escuro) ou claro (claro); passagem do cursor a 90% de opacidade.
- **Contorno:** transparente com borda de campo; passagem do cursor em superfície suave.
- **Fantasma / ícone:** sem borda; passagem do cursor em superfície suave; botão de ícone de 40 px sempre com `aria-label`.
- **Foco:** contorno de 2 px na cor de acento com deslocamento de 2 px. Desabilitado a 60% de opacidade.

### 7.2 Cartões e contêineres
- **Estilo de canto:** 10 px.
- **Fundo:** superfície; borda de 1 px no divisor.
- **Espaçamento interno:** 24 px.

### 7.3 Campos
- **Estilo:** transparente, borda de campo de 1 px, 40 px de altura, cantos de 0,5 rem.
- **Foco:** contorno de acento de 2 px.
- **Erro / desabilitado:** borda na cor de erro com `aria-invalid` e mensagem com `role="alert"`; desabilitado a 60%.

### 7.4 Navegação
Barra lateral de 15 rem com marca, lista de itens e rodapé com usuário, tema e saída. Item ativo em superfície suave com texto de acento; passagem do cursor em superfície suave. Abaixo de `md` vira faixa horizontal.

## 8. Faça e não faça

### 8.1 Faça
- **Fazer:** usar `transform` e `opacity` em qualquer animação, com duração curta, e respeitar `prefers-reduced-motion`.
- **Fazer:** manter foco visível e operação completa por teclado em todo controle.
- **Fazer:** mostrar estados vazio, carregando, erro e sucesso em toda tela.
- **Fazer:** reservar o laranja ao ativo, à ação primária e ao foco.
- **Fazer:** manter o mesmo pacote de renderização para a prévia e o vídeo final quando a legenda entrar no frontend.

### 8.2 Não faça
- **Não fazer:** usar cartão centralizado genérico como composição de tela. A tela de login atual ainda o usa e deve ser redesenhada na etapa de marca.
- **Não fazer:** usar gradiente roxo, nem gradientes decorativos.
- **Não fazer:** usar ícones decorativos sem função; ícone só substitui texto quando há `aria-label`.
- **Não fazer:** usar animação que atrase o trabalho: nada de transição que bloqueie a próxima ação.
- **Não fazer:** introduzir sombras, cartões aninhados ou uma segunda cor de destaque.
