<!-- epic: 🎨 Sprint 3 — Modelos de legenda (.ass) e vídeo com legenda gravada | labels: epic, sprint-3, legendas -->
## 🎯 Objetivo da Sprint

Entregar legendas **com estilo**: temas prontos (fonte, cor, contorno, destaque de palavra, karaokê) e a opção de baixar o **vídeo final com a legenda já gravada** na imagem.

## ⚠️ Limitação importante (por que `.ass`)

| Formato | Guarda texto + tempo | Guarda emoji | Guarda cor/fonte/animação | O CapCut importa? |
|---|---|---|---|---|
| `.srt` | ✅ | ✅ | ❌ | ✅ (só texto) |
| `.ass` | ✅ | ✅ | ✅ | ❌ |
| Vídeo com legenda gravada | — | ✅ | ✅ | ✅ (é só um vídeo) |

Ou seja: o **`.srt` continua sendo o arquivo para editar no CapCut** (o estilo é aplicado lá, em "Legendas → selecionar todas → Estilo"). O **`.ass` + FFmpeg** gera o vídeo pronto, com o modelo aplicado, para quem quer pular a edição.

## ✅ Definição de pronto (DoD)

- [ ] Gerador `.ass` a partir do `transcript.json`.
- [ ] Pelo menos 4 temas prontos, definidos em arquivos (fácil criar novos).
- [ ] Render do vídeo com a legenda gravada (opcional), com progresso.
- [ ] Prévia rápida antes do render completo.
- [ ] Download de todos os arquivos (SRT, ASS, vídeo) num ZIP.

## 📋 Tarefas

As tarefas estão listadas como sub-issues abaixo.

<!-- issue: [S3] Gerador de legenda .ass a partir do transcript.json | labels: enhancement, legendas, sprint-3 -->
## 🧩 Contexto

O `.ass` (Advanced SubStation Alpha) é o formato de legenda usado pelo FFmpeg/libass para desenhar legendas estilizadas: fonte, tamanho, cor, contorno, sombra, posição e efeitos **por palavra**.

## 🛠️ O que fazer

1. `app/captions/ass_writer.py` com `write_ass(transcript, blocos, tema, video_info, caminho)`.
2. Ler a resolução do vídeo com `ffprobe` e usar como `PlayResX`/`PlayResY`. Isso garante que o tamanho da fonte fique proporcional em 1080×1920 ou 1920×1080.
3. Estrutura do arquivo:
   - `[Script Info]`: `ScriptType: v4.00+`, `PlayResX`, `PlayResY`, `WrapStyle: 2`;
   - `[V4+ Styles]`: estilo `Default` vindo do tema + estilo `Highlight`;
   - `[Events]`: uma linha `Dialogue` por bloco de legenda.
4. Converter tempos para o formato ASS: `H:MM:SS.cc` (centésimos).
5. Converter cores do tema (`#FFD700`) para o formato ASS `&H00BBGGRR` (ordem invertida + alfa).
6. Escapar caracteres especiais (`{`, `}`, `\`) do texto.
7. Palavras com `highlight: true` recebem uma tag inline de cor: `{\c&H0000D7FF&}DINHEIRO{\r}`.
8. Emojis: anotar que a renderização depende de uma fonte com emoji (Noto Color Emoji). Ver a tarefa de render.

## 💡 Exemplo de saída

```
[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Montserrat Black,90,&H00FFFFFF,&H0000D7FF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,6,2,2,60,60,420,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.10,0:00:01.90,Default,,0,0,0,,como {\c&H0000D7FF&}GANHAR DINHEIRO{\r} 💰
```

## ✅ Critérios de aceite

- [ ] O `.ass` gerado abre corretamente no VLC/mpv e no Aegisub.
- [ ] Testes unitários: conversão de cor, de tempo e escape de texto.
- [ ] Fonte proporcional em vídeos verticais e horizontais.

## 🔗 Dependências

Sprint 0 (pipeline), Sprint 1 (blocos), Sprint 2 (destaques, opcional).

<!-- issue: [S3] Sistema de temas de legenda (Hormozi, Minimalista, Karaokê, Neon) | labels: enhancement, legendas, sprint-3 -->
## 🧩 Contexto

O usuário escolhe um "modelo" num menu, sem mexer em código. Cada tema é um arquivo de configuração.

## 🛠️ O que fazer

1. Pasta `app/themes/` com um arquivo YAML/JSON por tema, validado por um schema Pydantic `Theme`.
2. Campos do tema:
   ```yaml
   name: Hormozi
   description: Amarelo e branco, fonte grossa, 2–3 palavras, destaque na palavra falada
   font: Montserrat Black
   font_size_pct: 4.7        # % da altura do vídeo
   uppercase: true
   primary_color: "#FFFFFF"
   highlight_color: "#FFD700"
   outline_color: "#000000"
   outline_px: 6
   shadow_px: 2
   position: bottom          # top | middle | bottom
   margin_v_pct: 22          # distância da borda (área segura do Reels)
   caption_mode: short
   max_words: 3
   effect: active_word       # none | active_word | karaoke | pop
   ```
3. Efeitos:
   - `none`: bloco estático;
   - `active_word`: a palavra **sendo falada** muda de cor. Gerar uma linha `Dialogue` por palavra dentro do bloco, cada uma com a palavra ativa destacada;
   - `karaoke`: tags `{\kf<centésimos>}` por palavra (preenchimento progressivo da cor);
   - `pop`: animação de escala na entrada (`{\fscx80\fscy80\t(0,80,\fscx100\fscy100)}`).
4. Temas iniciais:
   - **Hormozi**: branco + amarelo, Montserrat Black, maiúsculas, `active_word`;
   - **Minimalista**: branco, fonte média, sem contorno pesado, caixa semitransparente (`BorderStyle=3`), frases;
   - **Karaokê**: preenchimento progressivo;
   - **Neon**: ciano/rosa com brilho (blur no contorno: `{\blur3}`).
5. Fontes: incluir os arquivos `.ttf` livres (Google Fonts, licença OFL) em `assets/fonts/`, junto com a licença.
6. `GET /api/v1/themes` lista os temas (nome, descrição, imagem de prévia).
7. Frontend: galeria de temas com a imagem de prévia de cada um (`assets/themes/<tema>.png`).

## ✅ Critérios de aceite

- [ ] Criar um tema novo = adicionar um arquivo YAML (sem mudar código).
- [ ] Tema inválido é rejeitado na inicialização, com mensagem clara.
- [ ] Os 4 temas renderizam corretamente (prints anexados ao PR).

## 🔗 Dependências

Gerador `.ass`.

<!-- issue: [S3] Render do vídeo final com legenda gravada (FFmpeg + libass) | labels: enhancement, editor, sprint-3 -->
## 🧩 Contexto

Com o `.ass` pronto, o FFmpeg "desenha" a legenda sobre o vídeo e gera um `.mp4` final, pronto para postar.

## 🛠️ O que fazer

1. Etapa `app/pipeline/steps/render.py` (roda se `options.burn_subtitles`).
2. **Não apagar o vídeo original** antes do render. Ajustar a limpeza da task para apagar só no fim do pipeline.
3. Comando base:
   ```bash
   ffmpeg -y -i entrada.mp4 \
     -vf "ass=legenda.ass:fontsdir=assets/fonts" \
     -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p \
     -c:a aac -b:a 192k -movflags +faststart \
     -progress pipe:1 -nostats \
     saida.mp4
   ```
4. **Progresso real**: ler `out_time_ms=` do `-progress pipe:1` e dividir pela duração (via `ffprobe`) para alimentar o `ProgressReporter`.
5. **Caminhos no Windows**: o filtro `ass=` exige escapar `\` e `:` (`C\:/pasta/legenda.ass`). Criar o helper `ffmpeg_filter_path()` com teste.
6. **Emojis**: a libass não desenha emoji colorido em todas as versões. Testar com a fonte Noto Color Emoji. Se não funcionar, plano B: renderizar os emojis como imagens PNG (Twemoji, licença CC-BY) e sobrepor com o filtro `overlay` nos tempos certos. Documentar a decisão.
7. Configurações: `RENDER_PRESET`, `RENDER_CRF`, `RENDER_HW_ACCEL` (`none` | `nvenc`: usar `h264_nvenc` quando houver GPU NVIDIA).
8. Reaproveitar `subprocess` com lista de argumentos (nunca `shell=True`).
9. Timeout coerente com a duração do vídeo.

## ✅ Critérios de aceite

- [ ] O vídeo final toca no celular e é aceito pelo Instagram/TikTok/YouTube (H.264 + AAC + yuv420p + faststart).
- [ ] A barra de progresso avança durante o render.
- [ ] Funciona no Windows (caminhos com espaços e acentos).
- [ ] A decisão sobre emojis está documentada.

## 🔗 Dependências

Gerador `.ass` e temas.

<!-- issue: [S3] Posição, tamanho e área segura da legenda configuráveis | labels: enhancement, legendas, sprint-3 -->
## 🧩 Contexto

No Reels/TikTok, a interface do app (botões, descrição, nome do perfil) cobre a parte de baixo e a lateral direita do vídeo. Uma legenda muito baixa fica escondida.

## 🛠️ O que fazer

1. Opções do job que **sobrescrevem** o tema: `caption_position: top | middle | bottom`, `caption_size: small | medium | large`, `caption_margin_pct`.
2. Predefinição "Área segura para Reels/TikTok": margem inferior de ~22% e margem lateral de ~8%.
3. Overlay opcional de "guia de área segura" na prévia (só na prévia, nunca no vídeo final).
4. Frontend: seletores simples (Cima / Meio / Baixo; Pequena / Média / Grande).

## ✅ Critérios de aceite

- [ ] As mudanças aparecem na prévia e no render.
- [ ] O padrão para vídeo vertical já respeita a área segura.

## 🔗 Dependências

Temas.

<!-- issue: [S3] Prévia rápida da legenda (frame e trecho de 5 s) | labels: enhancement, frontend, sprint-3 -->
## 🧩 Contexto

Renderizar um vídeo de 10 min só para descobrir que a fonte ficou grande demais é frustrante. O usuário precisa ver o resultado **antes**.

## 🛠️ O que fazer

1. Endpoint `POST /api/v1/preview/{job_id}` com `{ "theme": "...", "position": "...", "at": 12.5 }`.
2. Ele gera:
   - um **PNG** de um frame no instante `at`, com a legenda desenhada: `ffmpeg -ss 12.5 -i video -vf ass=... -frames:v 1 preview.png`;
   - opcional: um **trecho de 5 s** em baixa resolução (`-t 5 -vf scale=-2:640,ass=...`).
3. Para isso, o vídeo original e o transcript precisam continuar disponíveis depois da transcrição (respeitando a retenção da Sprint 0).
4. Escolher automaticamente um instante "bom" para a prévia, onde há fala e o bloco é longo.
5. Frontend: depois da transcrição, mostrar a prévia + o seletor de tema. Trocar o tema atualiza a prévia, e o botão "Renderizar vídeo final" dispara o render.

> Isso muda o fluxo: **transcrever** e **renderizar** passam a ser duas tasks separadas. A primeira para depois de gerar transcript + SRT; a segunda (render) é disparada pelo usuário.

## ✅ Critérios de aceite

- [ ] A prévia em PNG fica pronta em menos de 3 s num vídeo 1080p.
- [ ] Trocar o tema não refaz a transcrição.

## 🔗 Dependências

Render do vídeo final.

<!-- issue: [S3] Download de múltiplos arquivos e pacote ZIP | labels: enhancement, sprint-3 -->
## 🧩 Contexto

Agora um job pode gerar vários arquivos: `legenda.srt`, `legenda.ass`, `video_final.mp4`, `transcript.json` e, no futuro, clipes e textos. O endpoint atual só baixa o SRT.

## 🛠️ O que fazer

1. `GET /api/v1/jobs/{job_id}/files` lista os arquivos disponíveis (nome, tipo, tamanho).
2. `GET /api/v1/download/{job_id}/{kind}`, com `kind` em uma **lista fechada** (`srt`, `ass`, `video`, `transcript`, `zip`...). Nunca aceitar um nome de arquivo livre (path traversal).
3. `kind=zip` monta um ZIP em streaming (`zipfile` + `StreamingResponse`) com tudo.
4. Vídeos grandes: `FileResponse` já suporta download parcial (*Range requests*). Verificar.
5. Manter `GET /api/v1/download/{job_id}` (SRT) por compatibilidade.
6. Frontend: um botão por arquivo + "Baixar tudo (.zip)".

## ✅ Critérios de aceite

- [ ] `kind` inválido → 400; arquivo inexistente → 404.
- [ ] O ZIP abre no Windows com os nomes de arquivo corretos.

## 🔗 Dependências

Limpeza/organização por job (Sprint 0).
