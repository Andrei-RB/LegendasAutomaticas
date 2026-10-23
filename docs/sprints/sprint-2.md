<!-- epic: 📡 S2 — Sinais ricos e perfis de conteúdo | labels: epic, sprint-2 -->
**Objetivo:** detectar bons momentos com vários sinais e medir a qualidade.

**Pronto quando:** a nota heurística fica igual ou melhor que a do S1 no conjunto de ouro.

<!-- issue: [S2] Sinais de áudio: risadas/aplausos (PANNs) e entonação (librosa) | labels: backend, cortes, sprint-2 -->
**Objetivo:** extrair sinais do áudio a cada segundo.

- [ ] PANNs CNN14: probabilidade de risada, aplauso, grito e música por segundo.
- [ ] librosa: volume, variação de tom, palavras por segundo e pausas.

**Aceite:** um trecho de teste com risada é detectado.

<!-- issue: [S2] Sinais de vídeo: cenas (PySceneDetect) e rostos (MediaPipe) | labels: backend, cortes, sprint-2 -->
**Objetivo:** extrair sinais da imagem.

- [ ] `AdaptiveDetector` aplicado ao proxy.
- [ ] Rostos a 5 fps: caixa, rastreamento e abertura de boca.

**Aceite:** os cortes de cena e os rostos aparecem no `features.parquet`.

<!-- issue: [S2] Diarização (pyannote) com reserva | labels: backend, ia, sprint-2 -->
**Objetivo:** saber quem fala em cada momento (perfil podcast).

- [ ] pyannote com `HF_TOKEN`; o modelo é baixado em tempo de execução, nunca dentro da imagem.
- [ ] Reserva sem token: falante estimado por movimento de boca × volume.

**Aceite:** num podcast de teste, a troca de falante fica certa em ≥ 85% dos casos.

<!-- issue: [S2] Linha do tempo de features + pesos por perfil | labels: backend, cortes, sprint-2 -->
**Objetivo:** juntar os sinais e dar nota por perfil.

- [ ] `features.parquet` por segundo, com o falante ativo.
- [ ] Pesos por perfil (podcast, 1 pessoa, gameplay, vlog), num arquivo de configuração.
- [ ] A nota dos candidatos passa a usar todos os sinais.

**Aceite:** trocar o perfil muda a ordem dos candidatos de forma coerente.

<!-- issue: [S2] Filtro de alucinação do Whisper | labels: backend, legendas, sprint-2 -->
**Objetivo:** remover texto que o Whisper inventa.

- [ ] Remover frases fantasmas ("Legendas pela comunidade Amara.org", "Obrigado por assistir"), repetições e texto em trecho sem fala.

**Aceite:** um vídeo com silêncio no final não gera texto falso.

<!-- issue: [S2] Conjunto de ouro + métricas (precision@N, WER) | labels: testes, sprint-2 -->
**Objetivo:** medir a qualidade com números.

- [ ] `backend/avaliacao/ouro/`: 8 a 10 vídeos com 5 a 10 momentos marcados à mão (os vídeos ficam fora do git).
- [ ] `make avaliar`: precision@N, recall@N, WER e relatório curto.

**Aceite:** o relatório com a linha de base fica salvo no repositório.

<!-- issue: [S2] Linha do tempo com forma de onda, mapa de calor e miniaturas | labels: frontend, sprint-2, ui -->
**Objetivo:** mostrar os sinais no editor.

- [ ] Endpoints `forma-onda`, `mapa-calor` e `miniaturas`.
- [ ] Linha do tempo em canvas com zoom e trilhas.
- [ ] Seletor de perfil na tela Enviar.

**Aceite:** dá para ver os picos de risada na linha do tempo.
