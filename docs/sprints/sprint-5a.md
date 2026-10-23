<!-- epic: ✍️ S5a — Legendas: precisão e inteligência | labels: epic, sprint-5, legendas -->
**Objetivo:** legenda certa, sincronizada e "inteligente" (destaques, emojis, censura).

**Pronto quando:** o WER depois da correção fica ≤ ao WER do Whisper, o erro de sincronia mediano fica < 80 ms e o SRT abre no CapCut.

<!-- issue: [S5a] Alinhamento fino por corte (MMS forced aligner) | labels: legendas, backend, sprint-5 -->
**Objetivo:** fazer a palavra acender na hora exata (karaokê e palavra por palavra).

- [ ] torchaudio MMS forced aligner, aplicado só nos cortes escolhidos.
- [ ] Re-snap dos tempos no `DocumentoLegenda`.

**Aceite:** erro mediano < 80 ms numa amostra marcada à mão.

<!-- issue: [S5a] Correção com índices preservados (Qwen) | labels: legendas, ia, sprint-5 -->
**Objetivo:** corrigir palavras sem mexer nos tempos.

- [ ] Mesmos índices e mesma quantidade de itens.
- [ ] Mudança > 40% (distância de edição) mantém a palavra original.
- [ ] Diff salvo (para desfazer no editor).

**Aceite:** se o mock devolver itens a menos, o original é mantido; os tempos nunca mudam.

<!-- issue: [S5a] 4 modos de blocos (TS e Python iguais) | labels: legendas, sprint-5 -->
**Objetivo:** montar os blocos de cada modo de legenda.

- [ ] Modos: palavra, frase curta (2–4 palavras, ≤ 18 caracteres), karaokê e frase completa (≤ 42 caracteres por linha, 2 linhas).
- [ ] Função pura em Python e em TS, com teste que compara as duas saídas.

**Aceite:** os mesmos blocos nas duas linguagens para 10 transcrições de teste.

<!-- issue: [S5a] Enriquecimento por IA: cor por significado, emoji, momentos-chave | labels: legendas, ia, sprint-5 -->
**Objetivo:** destacar palavras de forma viral.

- [ ] 1 chamada ao Qwen por corte, que devolve por índice:
  - categoria (dinheiro, alerta, surpresa, emoção, padrão), em no máximo ~15% das palavras;
  - emoji válido;
  - 2–3 momentos-chave;
  - modelo sugerido.
- [ ] Reserva: dicionário de regras.

**Aceite:** emoji inválido é descartado; a densidade de destaques respeita o limite.

<!-- issue: [S5a] Censura de palavrões + beep | labels: legendas, render, sprint-5 -->
**Objetivo:** não perder alcance por causa de palavrões.

- [ ] Lista PT-BR configurável → texto com asterisco (`p*rra`).
- [ ] Beep opcional no áudio, no tempo da palavra.

**Aceite:** a palavra aparece censurada no SRT e no vídeo, e o beep cai no tempo certo.

<!-- issue: [S5a] Legenda que desvia do rosto (área segura) | labels: legendas, sprint-5 -->
**Objetivo:** a legenda nunca cobrir o rosto nem a interface do app.

- [ ] Calcular `posicao_y` por bloco a partir dos rostos + `enquadramento.json`.
- [ ] Respeitar as margens da área segura do TikTok, Reels e Shorts.

**Aceite:** num vídeo de teste, nenhum bloco sobrepõe o rosto.

<!-- issue: [S5a] SRT nos 4 modos + trilha de palavras no editor | labels: legendas, frontend, sprint-5, ui -->
**Objetivo:** exportar e editar a legenda.

- [ ] `legenda_<modo>.srt` com emojis, destaques em MAIÚSCULAS e censura.
- [ ] Editor: trilha de palavras (editar texto, tempo, destaque, emoji e censura), com salvamento automático e versão.

**Aceite:** os 4 SRTs importam no CapCut; uma edição no editor aparece no SRT.
