<!-- epic: 🚀 S1 — Fatia vertical ponta a ponta | labels: epic, sprint-1 -->
**Objetivo:** fazer o fluxo inteiro funcionar de forma simples: vídeo → cortes → legenda → MP4 + SRT.

**Pronto quando:** um vídeo de 1 h vira N cortes 9:16 com legenda, baixáveis pela interface.

<!-- issue: [S1] Ingestão: upload retomável, ffprobe, proxy e áudio | labels: backend, sprint-1 -->
**Objetivo:** receber o vídeo e prepará-lo para análise.

- [ ] Upload retomável (tus ou em partes) para arquivos de 1 a 4 GB.
- [ ] Validação real com ffprobe (precisa ter stream de vídeo e áudio; até 1 h, configurável).
- [ ] Proxy em 480p com keyframe a cada 1 s, `audio.wav` 16k mono, picos da forma de onda e sprite de miniaturas.

**Aceite:** um arquivo falso é rejeitado; um vídeo real gera todos os artefatos.

<!-- issue: [S1] Transcrição com Whisper large-v3-turbo (GPU) | labels: backend, ia, sprint-1 -->
**Objetivo:** gerar a transcrição com tempo por palavra.

- [ ] `transcricao.json` com palavras (texto, início, fim, prob) e frases (IDs).
- [ ] Modelo, idioma (`pt`) e vocabulário configuráveis.
- [ ] VAD ligado.
- [ ] Liberar a VRAM depois de usar.

**Aceite:** 1 h de vídeo transcrita em menos de 8 min na RTX 4060 Ti.

<!-- issue: [S1] Candidatos alinhados a frases + nota de energia | labels: backend, cortes, sprint-1 -->
**Objetivo:** gerar janelas de corte usando só código.

- [ ] Janelas que começam e terminam em frase, com duração dentro do alvo ±20%.
- [ ] Nota simples: energia do áudio + densidade de fala.
- [ ] Remover sobreposições (IoU > 0,3) e ficar com o top `max(4N, 30)`.
- [ ] 3 variantes de início e 3 de fim por candidato.

**Aceite:** nenhum candidato corta palavra ou começa no meio de uma frase (teste).

<!-- issue: [S1] Triagem com Qwen local (Ollama) | labels: ia, cortes, sprint-1 -->
**Objetivo:** dar nota aos candidatos com IA local.

- [ ] Rubrica de 0 a 10 (gancho, contexto, desfecho, emoção, clareza) em JSON schema.
- [ ] A resposta traz só o `candidato_id` e uma citação literal.
- [ ] Validar o JSON; se vier inválido, descartar.
- [ ] Os N melhores viram cortes para revisão.

**Aceite:** um ID inventado pela IA é rejeitado (teste com mock).

<!-- issue: [S1] API e telas: enviar, análise, galeria, editor mínimo | labels: backend, frontend, sprint-1, ui -->
**Objetivo:** permitir usar o fluxo pela interface.

- [ ] Telas: Enviar (perfil, duração, N) e Análise (etapas ao vivo + notificação do navegador).
- [ ] Galeria com nota e motivo.
- [ ] Editor mínimo: Player Remotion + alças de início e fim alinhadas à palavra (o servidor revalida).

**Aceite:** dá para ajustar o início de um corte e o ajuste fica salvo.

<!-- issue: [S1] Legenda e render básicos (Remotion + ffmpeg) | labels: legendas, render, sprint-1 -->
**Objetivo:** gerar o primeiro vídeo final com legenda.

- [ ] `DocumentoLegenda` básico (palavras do corte).
- [ ] Pacote `pacotes/modelos-legenda` com 1 modelo (Bold), modo frase curta.
- [ ] Serviço `render`: camada de legenda com alfa.
- [ ] ffmpeg: recorte central 9:16 + sobreposição da camada + x264 CRF 17 + `loudnorm`.
- [ ] Exportar o SRT (frase curta).

**Aceite:** o MP4 toca no celular e o SRT importa sincronizado no CapCut.
