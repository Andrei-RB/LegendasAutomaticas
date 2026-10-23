<!-- epic: 🎨 S5b — Legendas: modelos virais e editor | labels: epic, sprint-5, legendas, frontend -->
**Objetivo:** ter um catálogo de modelos bonitos e virais e um editor visual, com a prévia igual ao vídeo final.

**Pronto quando:** os 8 modelos × 4 modos renderizam igual na prévia e no MP4 (teste de comparação de frames).

<!-- issue: [S5b] Schema EspecModelo (JSON versionado) | labels: legendas, sprint-5 -->
**Objetivo:** descrever a aparência de qualquer modelo num formato único.

- [ ] Campos:
  - texto: fonte, tamanho, caixa alta;
  - cores: cor base, paleta por categoria;
  - acabamento: contorno, sombra, neon, gradiente, caixa de fundo;
  - palavra ativa e animação (tipo × intensidade);
  - emoji (inline, sticker ou ambos);
  - posição e área segura;
  - densidade de destaques;
  - elementos.
- [ ] Validação com Zod (TS) e Pydantic (Python) a partir do mesmo JSON Schema.

**Aceite:** um modelo inválido é recusado nos dois lados.

<!-- issue: [S5b] 8 modelos de sistema | labels: legendas, frontend, sprint-5, ui -->
**Objetivo:** catálogo inicial de modelos.

- [ ] Bold/Hormozi, MrBeast, Karaokê, Caixa, Minimal, Clean, Neon e Gradiente, em `pacotes/modelos-legenda/modelos/`.
- [ ] Cada modelo funciona nos 4 modos.

**Aceite:** prints dos 8 × 4 anexados ao PR.

<!-- issue: [S5b] Animações, emojis Noto e elementos virais | labels: legendas, render, sprint-5 -->
**Objetivo:** dar o visual "viral" aos modelos.

- [ ] Animações pop, bounce, slide, fade, typewriter e shake × sutil, normal ou forte.
- [ ] Emoji como imagem Noto: inline e sticker grande nos momentos-chave.
- [ ] Elementos: título-gancho (3 s), barra de progresso, @ do perfil e CTA final.

**Aceite:** o emoji é idêntico no Windows (prévia) e no MP4.

<!-- issue: [S5b] Fontes: catálogo OFL + upload | labels: legendas, backend, sprint-5 -->
**Objetivo:** oferecer boas fontes com licença segura.

- [ ] ~12 fontes OFL em `recursos/fontes/`, com as licenças.
- [ ] Upload de `.ttf`/`.otf` (extensão, tamanho e `fontTools` validando).
- [ ] Fontes servidas para a prévia e para o render.

**Aceite:** uma fonte enviada aparece na prévia e no vídeo final.

<!-- issue: [S5b] Galeria de modelos no editor do corte | labels: frontend, sprint-5, ui -->
**Objetivo:** escolher o modelo vendo o próprio corte.

- [ ] Aba Modelo: 8 cards + "Meus modelos", com prévia ao passar o mouse (um Player por vez).
- [ ] Destaque para o modelo sugerido pela IA.

**Aceite:** trocar o modelo atualiza a prévia na hora.

<!-- issue: [S5b] Editor visual de modelos (/modelos) | labels: frontend, sprint-5, ui -->
**Objetivo:** criar e editar modelos próprios.

- [ ] Controles de todos os campos do `EspecModelo`, com prévia ao vivo.
- [ ] Duplicar um modelo de sistema e salvar como "Meus modelos" (API `GET/POST /modelos`).

**Aceite:** um modelo criado aparece na galeria e no render.

<!-- issue: [S5b] Teste de fidelidade prévia × vídeo final | labels: testes, render, sprint-5 -->
**Objetivo:** garantir que a prévia é igual ao vídeo final.

- [ ] Capturar frames do Player e do MP4 nos mesmos instantes e comparar (SSIM ≥ limiar).

**Aceite:** o teste roda no CI com 1 modelo e localmente com todos.
