<!-- epic: 🔊 Sprint 5 — Áudio e formato (ruído, volume, música, vertical, zoom) | labels: epic, sprint-5, editor, audio -->
## 🎯 Objetivo da Sprint

Deixar o vídeo com **cara de profissional** sem o usuário abrir outro programa:

- áudio limpo e no volume padrão das redes sociais;
- música de fundo que abaixa sozinha quando a pessoa fala;
- conversão automática de vídeo deitado (16:9) para vertical (9:16), seguindo o rosto;
- zoom automático em momentos de impacto.

## ✅ Definição de pronto (DoD)

- [ ] Todas as opções são independentes e opcionais.
- [ ] Todas as etapas de vídeo são combinadas no **menor número possível de encodes** (idealmente 1).
- [ ] Antes/depois de cada feature documentado no PR (áudio/print).

## 📋 Tarefas

As tarefas estão listadas como sub-issues abaixo.

<!-- issue: [S5] Redução de ruído do áudio | labels: enhancement, audio, sprint-5 -->
## 🧩 Contexto

Vídeos gravados com celular têm chiado, ventilador, ar-condicionado e eco. Limpar o áudio melhora a experiência **e** a precisão do Whisper.

## 🛠️ O que fazer

1. Opção `denoise: "off" | "light" | "strong"`.
2. Implementação em níveis:
   - **light**: filtro FFmpeg `afftdn=nf=-25` + `highpass=f=80` (remove ronco grave);
   - **strong**: filtro `arnndn` com um modelo RNNoise (`.rnnn`, arquivo em `assets/rnnoise/`, verificar a licença) ou, como alternativa, o modelo **Demucs/DeepFilterNet** em Python (mais pesado e mais eficaz). Medir e decidir.
3. Aplicar **antes** da transcrição numa cópia do áudio (melhora o Whisper) **e** no áudio final do vídeo.
4. Rodar o benchmark da Sprint 1 com e sem redução de ruído e registrar se o WER melhora.

## ✅ Critérios de aceite

- [ ] Arquivo de teste com ruído de fundo fica audivelmente mais limpo (anexar antes/depois ao PR).
- [ ] A voz não fica "metálica" no modo light.

## 🔗 Dependências

Sprint 4 (motor de corte, para aplicar os filtros no encode final).

<!-- issue: [S5] Normalização de volume (loudness -14 LUFS) | labels: enhancement, audio, sprint-5 -->
## 🧩 Contexto

Cada plataforma ajusta o volume dos vídeos para um padrão (~-14 LUFS). Vídeos muito baixos parecem "fracos"; muito altos são comprimidos e distorcem. Normalizar resolve.

## 🛠️ O que fazer

1. Opção `normalize_audio: bool` (padrão **ligado** quando há render).
2. Usar o `loudnorm` em **duas passadas** (mais preciso):
   - 1ª passada: `-af loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json -f null -`, lendo o JSON de medição do stderr;
   - 2ª passada: aplicar com `measured_I`, `measured_TP`, `measured_LRA`, `measured_thresh` e `offset`.
3. Configurável: `TARGET_LUFS` (-14 redes sociais, -16 podcast).
4. Combinar com os outros filtros de áudio na mesma cadeia: `denoise → loudnorm`.

## ✅ Critérios de aceite

- [ ] O vídeo final medido com `ebur128` dá -14 ±1 LUFS.
- [ ] Teste unitário do parser do JSON do loudnorm.

## 🔗 Dependências

Nenhuma além do motor de render.

<!-- issue: [S5] Música de fundo com ducking automático | labels: enhancement, audio, sprint-5 -->
## 🧩 Contexto

Música de fundo deixa o vídeo mais dinâmico, mas não pode atrapalhar a voz. *Ducking* = a música **abaixa sozinha** quando alguém fala e volta quando a pessoa para.

## 🛠️ O que fazer

1. Biblioteca de músicas **livres de direitos** em `assets/music/` (com um arquivo `CREDITS.md` de licença por faixa), organizada por clima: animada, calma, motivacional, suspense.
2. Opção para o usuário **enviar a própria música** (mesma validação de upload: extensões `.mp3/.wav/.m4a`, limite de tamanho).
3. Opções: `music: str | None`, `music_volume: 0–100` (padrão 15), `music_ducking: bool`.
4. Cadeia FFmpeg:
   ```
   [1:a]aloop=loop=-1:size=2e9,volume=0.15[musica];
   [musica][voz]sidechaincompress=threshold=0.02:ratio=8:attack=20:release=400[musica_duck];
   [voz][musica_duck]amix=inputs=2:duration=first:normalize=0[audio_final]
   ```
   (`[voz]` precisa ser duplicada com `asplit`, porque é usada no sidechain e no mix.)
5. *Fade in* (1 s) no começo e *fade out* (2 s) no fim da música.
6. Aplicar **depois** dos cortes da Sprint 4 (a música não pode "pular" nos cortes).
7. Alternativa por IA (opcional): o Gemini escolhe o clima da música pela transcrição.

## ✅ Critérios de aceite

- [ ] Voz sempre inteligível; música perceptível nas pausas.
- [ ] A música faz loop se for mais curta que o vídeo e termina com fade.
- [ ] Todas as faixas incluídas têm licença documentada.

## 🔗 Dependências

Motor de corte (Sprint 4).

<!-- issue: [S5] Reenquadramento automático 16:9 → 9:16 seguindo o rosto | labels: enhancement, editor, sprint-5 -->
## 🧩 Contexto

Muitos criadores gravam na horizontal (podcast, webcam) e precisam postar na vertical. Cortar o centro da imagem nem sempre funciona: a pessoa pode estar de lado. O ideal é **seguir o rosto**.

## 🛠️ O que fazer

1. Opção `reframe: "off" | "center" | "face"` + `aspect: "9:16" | "1:1" | "4:5"`.
2. `center`: só o filtro `crop=ih*9/16:ih` centralizado (simples, sem IA).
3. `face`:
   - extrair frames em baixa resolução (ex.: 5 fps, 480p) com o FFmpeg;
   - detectar rostos com **MediaPipe Face Detection** (`pip install mediapipe`);
   - calcular o centro X do rosto principal (o maior/mais central) por frame;
   - **suavizar** a trajetória (média móvel ou filtro de Kalman + "zona morta": só mover a câmera se o rosto sair de uma margem). Sem isso, a imagem fica tremendo;
   - sem rosto detectado: manter a última posição ou centralizar;
   - gerar a expressão de crop por tempo, ou gerar segmentos com posições fixas e usar `sendcmd`/`crop` com `x` variável.
4. Também em vídeos com **duas pessoas** (podcast): na v1, focar em quem está falando é complexo. Documentar como melhoria futura (detectar o falante pela boca + áudio).
5. Posição da legenda: ajustar automaticamente para o novo formato.

## ✅ Critérios de aceite

- [ ] Um vídeo 16:9 de uma pessoa andando pelo quadro gera um 9:16 com o rosto sempre visível, sem tremedeira.
- [ ] O modo `center` funciona sem instalar o MediaPipe.

## 🔗 Dependências

Motor de render (Sprint 3/4).

<!-- issue: [S5] Zoom automático em momentos de impacto | labels: enhancement, editor, ia, sprint-5 -->
## 🧩 Contexto

Os "punch-ins" (zoom rápido de 100% para ~115%) em frases de impacto prendem a atenção. É uma das técnicas mais usadas em Shorts.

## 🛠️ O que fazer

1. Opção `auto_zoom: "off" | "subtle" | "dynamic"`.
2. **Escolha dos momentos**:
   - com Gemini: enviar a transcrição em blocos e pedir os índices das frases de impacto (`[{"start_i": 40, "end_i": 47, "intensity": 1.15}]`), no máximo 1 a cada ~8 s;
   - sem Gemini: heurística, ou seja, palavras destacadas (Sprint 2), pontos de exclamação ou mudança de tema.
3. **Aplicação**: alternar zoom de 1.0 e 1.12–1.2 por trecho, usando `crop` + `scale` com expressões dependentes de `t`, ou `zoompan` (mais caro). Centralizar o zoom no rosto se o reenquadramento estiver ativo.
4. Duas variações: **corte seco** (zoom instantâneo, estilo jump cut) e **suave** (rampa de 150 ms).
5. Não aplicar zoom em sequência (mínimo de 3 s entre zooms).

## ✅ Critérios de aceite

- [ ] Os zooms caem em frases que fazem sentido (avaliação manual em 3 vídeos).
- [ ] Sem perda de qualidade visível (aplicar o zoom sobre a resolução original antes de reduzir).

## 🔗 Dependências

Sprint 2 (Gemini, opcional), render.
