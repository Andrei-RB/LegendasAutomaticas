<!-- epic: 🎥 S4 — Câmera virtual (9:16 seguindo o rosto) | labels: epic, sprint-4, render -->
**Objetivo:** fazer o vertical seguir quem fala, sem tremer.

**Pronto quando:** não há tremedeira visível e a troca de câmera fica certa em ≥ 85% dos casos de teste.

<!-- issue: [S4] Trajetória da câmera (One-Euro + zona morta) | labels: render, backend, sprint-4 -->
**Objetivo:** calcular um movimento de câmera suave.

- [ ] Alvo: rosto do falante ativo.
- [ ] Filtro One-Euro, zona morta e velocidade máxima.
- [ ] Reiniciar a trajetória em corte de cena.
- [ ] Gerar `enquadramento.json` com keyframes.

**Aceite:** num vídeo de pessoa andando, o rosto fica sempre visível.

<!-- issue: [S4] Troca de câmera no podcast | labels: render, sprint-4 -->
**Objetivo:** focar em quem está falando.

- [ ] Usar a diarização + boca × volume, com histerese de 1 s.
- [ ] Sem rosto: manter a última posição ou centralizar.

**Aceite:** ≥ 85% das trocas certas no vídeo de teste.

<!-- issue: [S4] Render com recorte dinâmico | labels: render, sprint-4 -->
**Objetivo:** aplicar a câmera no vídeo final.

- [ ] Recorte por keyframes no ffmpeg, na mesma passada da sobreposição e do encode.
- [ ] Modo "manter original".

**Aceite:** um único encode, com qualidade igual ao S1.

<!-- issue: [S4] Aba Enquadramento no editor | labels: frontend, sprint-4, ui -->
**Objetivo:** permitir ajustar o enquadramento na interface.

- [ ] Opções: automático, manual (arrastar a janela) ou original.
- [ ] A prévia acompanha os keyframes.

**Aceite:** o ajuste manual aparece no MP4 final.
