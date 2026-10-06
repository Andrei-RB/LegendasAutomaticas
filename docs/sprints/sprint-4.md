<!-- epic: ✂️ Sprint 4 — Editor: cortes inteligentes (silêncios e vícios de fala) | labels: epic, sprint-4, editor -->
## 🎯 Objetivo da Sprint

Transformar o projeto num **editor automático**: o usuário envia o vídeo bruto e recebe de volta o vídeo **sem pausas e sem "é..., tipo, né"**, com a legenda **já sincronizada** com o vídeo cortado.

## 🧠 Ideia central

Já temos o tempo exato de cada palavra (Whisper). Então:

```
palavras:  [Olá 0.5–0.8] [pessoal 0.8–1.3] ......pausa 2s...... [hoje 3.3–3.6] [é 3.7–3.9] [vou 4.6–4.8]
manter:    [0.4 ─────────── 1.45]                               [3.2 ── 3.65]           [4.5 ── ...]
```

1. Calcular os **trechos a manter** (*keep segments*).
2. Cortar o vídeo e juntar esses trechos.
3. **Remapear** os tempos das legendas para a nova linha do tempo.

## ✅ Definição de pronto (DoD)

- [ ] Remoção de silêncios com limite configurável.
- [ ] Remoção de vícios de fala com lista configurável (+ ajuda do Gemini para casos ambíguos).
- [ ] Motor de corte com FFmpeg sem "estalos" no áudio.
- [ ] Legenda (SRT/ASS) perfeitamente sincronizada com o vídeo cortado.
- [ ] Relatório: "Removidos 47 s (18%) — 31 pausas, 12 vícios de fala".

## 📋 Tarefas

As tarefas estão listadas como sub-issues abaixo.

<!-- issue: [S4] Detectar silêncios e calcular trechos a manter (keep segments) | labels: enhancement, editor, sprint-4 -->
## 🧩 Contexto

Pausas longas deixam o vídeo lento. A forma mais precisa de achá-las no nosso caso é usar os **tempos das palavras**, que já temos: um intervalo grande entre o fim de uma palavra e o início da próxima é uma pausa.

## 🛠️ O que fazer

1. `app/editing/silence.py` com `calcular_trechos(words, duracao, min_silencio=0.5, margem=0.15)`.
2. Regras:
   - intervalo entre palavras > `min_silencio` é candidato a corte;
   - manter `margem` antes e depois da fala (não cortar o fim da palavra nem a respiração natural);
   - silêncio no começo e no fim do vídeo também é cortado;
   - juntar trechos de fala separados por menos de `2 × margem`;
   - descartar trechos a manter muito curtos (< 0,2 s), que geram cortes "picotados".
3. **Validação extra (opcional)**: confirmar com o filtro `silencedetect` do FFmpeg (`-af silencedetect=n=-35dB:d=0.5`), para não cortar risadas/sons sem palavra transcrita.
4. Opções do job: `remove_silences: bool`, `silence_min_s: float (0.3–2.0)`, `silence_margin_s: float (0.05–0.5)`.
5. Predefinições no frontend: **Suave** (0,8 s / margem 0,25), **Normal** (0,5 / 0,15), **Agressivo** ("jump cut", 0,3 / 0,08).
6. Salvar os trechos no `transcript.json` → `"cuts": {"keep": [[0.4, 1.45], [3.2, 3.65]], "removed_reason": [...]}`.

## ✅ Critérios de aceite

- [ ] Testes unitários com listas de palavras sintéticas cobrindo: começo/fim, pausas pequenas, margens e trechos minúsculos.
- [ ] Nenhuma palavra fica cortada pela metade.

## 🔗 Dependências

Sprint 0 (transcript.json), Sprint 1 (tempos limpos).

<!-- issue: [S4] Remover vícios de fala (é, ãh, tipo, né...) | labels: enhancement, editor, ia, sprint-4 -->
## 🧩 Contexto

Vícios de linguagem ("é...", "ãh", "hum", "tipo", "né", "então...", "assim") deixam o vídeo menos profissional. O desafio é que algumas dessas palavras **também são palavras normais**:

- "Isso **é** importante" → o "é" é verbo, **não pode** cortar.
- "Hoje eu vou... **é**... falar" → o "é" é hesitação, **pode** cortar.

## 🛠️ O que fazer

1. Lista configurável `app/editing/fillers_pt.txt`, dividida em:
   - **sempre vício** (cortar direto): `ãh`, `ahn`, `hum`, `hmm`, `éé`, `ééé`, `ã`;
   - **ambíguos** (precisam de contexto): `é`, `tipo`, `né`, `então`, `assim`, `cara`, `bom`, `enfim`.
2. Regra local para os ambíguos: considerar vício quando estiver **isolado por pausas** (> 0,25 s antes e depois) ou **repetido** ("é é", "tipo tipo").
3. Com o Gemini ativo: enviar as frases que têm palavras ambíguas e pedir a classificação por índice: `[{"i": 37, "filler": true}]`. Isso pode ir na mesma chamada da revisão da Sprint 2.
4. Remover também **repetições/gaguejos**: "eu eu eu vou" → "eu vou" (mesma palavra repetida em sequência, com menos de 0,6 s entre elas).
5. As palavras marcadas viram trechos removidos e são combinadas com os cortes de silêncio.
6. As palavras removidas **somem da legenda** também.
7. Opção do job: `remove_fillers: bool` + lista extra definida pelo usuário.

## ✅ Critérios de aceite

- [ ] "Isso é importante" mantém o "é" (teste).
- [ ] "vou... é... falar" remove o "é" (teste).
- [ ] Funciona sem Gemini (só regras) e melhora com Gemini.

## 🔗 Dependências

Detectar silêncios; Sprint 2 (opcional).

<!-- issue: [S4] Motor de corte do vídeo com FFmpeg (sem estalos no áudio) | labels: enhancement, editor, sprint-4 -->
## 🧩 Contexto

Com a lista de trechos a manter, precisamos gerar o vídeo cortado. Cortar áudio "seco" causa **estalos** (*clicks*) nas emendas, então é preciso um micro *fade*.

## 🛠️ O que fazer

1. `app/editing/cutter.py` com `cortar_video(entrada, keep_segments, saida, reporter)`.
2. Estratégia recomendada: um único comando com `filter_complex` usando `trim`/`atrim` + `concat`:
   ```
   [0:v]trim=start=0.40:end=1.45,setpts=PTS-STARTPTS[v0];
   [0:a]atrim=start=0.40:end=1.45,asetpts=PTS-STARTPTS,afade=t=in:d=0.01,afade=t=out:st=1.04:d=0.01[a0];
   [0:v]trim=start=3.20:end=3.65,setpts=PTS-STARTPTS[v1];
   ...
   [v0][a0][v1][a1]...concat=n=N:v=1:a=1[outv][outa]
   ```
3. Com muitos cortes (> ~150), o comando fica gigante. Gravar o filtro num arquivo e usar `-filter_complex_script arquivo.txt`.
4. Alternativa para vídeos longos: cortar em pedaços e juntar com o *concat demuxer*. Avaliar desempenho.
5. Reencodar com os mesmos parâmetros do render (Sprint 3), para manter a compatibilidade.
6. **Combinar com a legenda gravada**: se `burn_subtitles`, aplicar o `ass=` **depois** do concat, no mesmo comando (um encode só, mais rápido e sem perda dupla de qualidade).
7. Progresso via `-progress pipe:1`, calculado sobre a **duração final**.
8. Gerar também `video_cortado.mp4` **sem** legenda, para quem quer editar no CapCut com o `.srt` remapeado.

## ✅ Critérios de aceite

- [ ] Nenhum estalo audível nas emendas (teste manual com fone).
- [ ] Áudio e vídeo continuam sincronizados até o final (testar com um vídeo de 10 min).
- [ ] Vídeo com 300 cortes processa sem erro de "argument list too long".

## 🔗 Dependências

Detectar silêncios.

<!-- issue: [S4] Remapear tempos da legenda para o vídeo cortado | labels: enhancement, editor, legendas, sprint-4 -->
## 🧩 Contexto

Depois do corte, a palavra que era dita em 3,3 s no vídeo original agora aparece em, por exemplo, 1,5 s. **Se não remapear, a legenda fica toda dessincronizada.** Este é o ponto mais crítico da Sprint.

## 🛠️ O que fazer

1. `app/editing/timeline.py`:
   ```python
   def remap(t: float, keep: list[tuple[float, float]]) -> float | None:
       """Converte um tempo do vídeo original para o vídeo cortado. None se t caiu num trecho removido."""
       acumulado = 0.0
       for ini, fim in keep:
           if t < ini:
               return None
           if t <= fim:
               return acumulado + (t - ini)
           acumulado += fim - ini
       return None
   ```
2. Aplicar a cada palavra (`start`/`end`). Palavras que caíram em trechos removidos (vícios) são descartadas.
3. Palavra parcialmente fora de um trecho: "grudar" o tempo na borda do trecho.
4. Gerar `transcript_editado.json` (mantendo também o original) e, a partir dele, `legenda.srt`/`legenda.ass` para o vídeo cortado.
5. Se o usuário **não** cortar, nada muda.

## ✅ Critérios de aceite

- [ ] Testes unitários: tempo antes, dentro, entre e depois dos trechos; bordas exatas.
- [ ] Teste de propriedade: a ordem das palavras se mantém e nenhum tempo remapeado passa da duração final.
- [ ] Verificação manual: legenda sincronizada no vídeo cortado do início ao fim.

## 🔗 Dependências

Motor de corte.

<!-- issue: [S4] Relatório de edição e revisão dos cortes antes de exportar | labels: enhancement, editor, frontend, sprint-4 -->
## 🧩 Contexto

O usuário precisa confiar no corte automático e poder desfazer um corte errado.

## 🛠️ O que fazer

1. Relatório ao fim do job (`outputs/<job_id>/edit_report.json` + exibição no frontend):
   - duração original × final, % removida;
   - número de pausas e de vícios removidos;
   - lista dos cortes com o motivo (`silence` / `filler` / `repeat`) e o texto ao redor.
2. Frontend: lista de cortes com uma caixa de seleção para **desfazer cortes específicos**, com o botão "Reprocessar só o corte" (sem refazer a transcrição).
3. Exportar a lista de cortes como **EDL** ou **XML (FCPXML)**, para quem quer abrir no DaVinci/Premiere com os cortes como pontos editáveis. É opcional e pode virar uma issue separada depois.

## ✅ Critérios de aceite

- [ ] Relatório coerente com o vídeo gerado.
- [ ] Desfazer um corte e reprocessar não refaz a transcrição nem chama o Gemini de novo.

## 🔗 Dependências

Remapear tempos.
