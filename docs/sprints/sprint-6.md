<!-- epic: 🚀 Sprint 6 — IA avançada (cortes virais, textos, capítulos, tradução, thumbnail) | labels: epic, sprint-6, ia -->
## 🎯 Objetivo da Sprint

Usar o Gemini para fazer o trabalho "criativo" que hoje o criador faz na mão:

- encontrar os **melhores trechos** de um vídeo longo para virar Shorts;
- escrever **título, descrição e hashtags**;
- gerar **capítulos** para o YouTube;
- **traduzir** as legendas;
- sugerir a **thumbnail**.

## ✅ Definição de pronto (DoD)

- [ ] Todas as features funcionam a partir do `transcript.json` existente (não precisa transcrever de novo).
- [ ] Respostas da IA validadas por schema; falhas tratadas sem derrubar o job.
- [ ] Cada feature pode ser executada **depois** do job principal (botão "Gerar..." na tela do resultado).

## 📋 Tarefas

As tarefas estão listadas como sub-issues abaixo.

<!-- issue: [S6] Cortes virais: encontrar os melhores trechos para Shorts/Reels | labels: enhancement, ia, editor, sprint-6 -->
## 🧩 Contexto

Transformar um vídeo longo (podcast, live, aula) em vários vídeos curtos é o recurso que ferramentas pagas como o Opus Clip cobram. Com a transcrição com tempos + Gemini, conseguimos fazer igual.

## 🛠️ O que fazer

1. Opção/ação: `viral_clips: { count: 1–10, min_s: 20, max_s: 60 }`.
2. Enviar ao Gemini a transcrição **segmentada em frases com índice e tempo** (`[{"s": 12, "t": "00:03:15", "text": "..."}]`). Vídeos de até ~2 h cabem na janela de contexto do modelo. Acima disso, dividir em partes.
3. Pedir de volta:
   ```json
   [{"start_s": 12, "end_s": 19, "title": "O erro que custa caro",
     "hook": "Primeira frase forte do clipe", "score": 87,
     "reason": "Tem gancho forte nos 3 primeiros segundos e conclusão clara"}]
   ```
4. Critérios no prompt: **gancho nos primeiros 3 s**, ideia completa (começo, meio e fim), entendível sem o resto do vídeo, emoção/curiosidade/valor prático, duração dentro do limite.
5. Validar: trechos dentro do vídeo, sem sobreposição, duração respeitada (ajustar para a borda da frase mais próxima).
6. Para cada clipe, reaproveitar o pipeline: cortar (Sprint 4) → reenquadrar 9:16 (Sprint 5) → legenda com tema (Sprint 3) → `clips/clip_01.mp4`, com título e score.
7. Frontend: galeria de clipes com player, título, nota, motivo e download individual/ZIP.

## ✅ Critérios de aceite

- [ ] Um vídeo de 20 min gera N clipes dentro dos limites de duração, começando e terminando em frases completas.
- [ ] Cada clipe tem legenda própria sincronizada (tempos relativos ao início do clipe).

## 🔗 Dependências

Sprints 2, 3 e 4 (e 5 para o vertical).

<!-- issue: [S6] Gerar título, descrição e hashtags por plataforma | labels: enhancement, ia, sprint-6 -->
## 🧩 Contexto

Depois de editar, o criador ainda precisa escrever o texto da postagem. A IA faz isso a partir da transcrição.

## 🛠️ O que fazer

1. Ação "Gerar textos" → `outputs/<job_id>/post.json` + exibição com botão "Copiar".
2. Saída por plataforma:
   - **YouTube**: 3 opções de título (até 70 caracteres), descrição com resumo + CTA, 10–15 tags;
   - **Instagram Reels**: legenda curta com gancho na 1ª linha, emojis, 5–10 hashtags;
   - **TikTok**: legenda curtíssima + 3–5 hashtags.
3. Opções: tom (`informal` | `profissional` | `divertido`), idioma, palavras/hashtags obrigatórias (ex.: @ do perfil).
4. Schema de resposta validado; limite de caracteres conferido no código (cortar e avisar se a IA passar).

## ✅ Critérios de aceite

- [ ] Textos respeitam os limites de cada plataforma.
- [ ] Reprocessar com outro tom não refaz a transcrição.

## 🔗 Dependências

Cliente Gemini (Sprint 2).

<!-- issue: [S6] Capítulos automáticos para YouTube | labels: enhancement, ia, sprint-6 -->
## 🧩 Contexto

Vídeos longos no YouTube com capítulos (`00:00 Introdução`) têm melhor retenção e aparecem divididos na busca.

## 🛠️ O que fazer

1. Ação "Gerar capítulos", disponível para vídeos com mais de 3 min.
2. Gemini recebe as frases com tempo e devolve `[{"start_s": 0, "title": "Introdução"}, ...]`.
3. Regras exigidas pelo YouTube: o primeiro capítulo começa em `00:00`, no mínimo 3 capítulos, cada um com pelo menos 10 s. Validar e corrigir no código.
4. Se houver cortes (Sprint 4), usar os tempos **remapeados**.
5. Saída em texto pronto para colar na descrição:
   ```
   00:00 Introdução
   01:42 O erro mais comum
   05:10 Como resolver em 3 passos
   ```

## ✅ Critérios de aceite

- [ ] A saída sempre cumpre as regras do YouTube (teste do validador).

## 🔗 Dependências

Cliente Gemini.

<!-- issue: [S6] Tradução de legendas mantendo a sincronia | labels: enhancement, ia, legendas, sprint-6 -->
## 🧩 Contexto

Legendas em inglês/espanhol aumentam o alcance. A tradução não pode ser palavra por palavra (a ordem das palavras muda entre idiomas), então a unidade de tradução é o **bloco de legenda** ou a **frase**.

## 🛠️ O que fazer

1. Opção `translate_to: list[str]` (ex.: `["en", "es"]`).
2. Traduzir por **frase** (segmento) com índice: `[{"s": 3, "text": "..."}]` → `[{"s": 3, "text": "..."}]`, com validação de mesma quantidade e mesmos índices.
3. Redistribuir a frase traduzida nos tempos do segmento original:
   - modo `sentence`: o bloco inteiro com o tempo da frase;
   - modo `short`/`word`: dividir a frase traduzida em pedaços de 2–3 palavras, distribuindo o tempo **proporcionalmente ao número de caracteres**.
4. Gerar `legenda.en.srt`, `legenda.es.srt` (e `.ass`, se houver tema).
5. Prompt com instrução de tom (manter gírias/informalidade) e de manter nomes próprios e termos do vocabulário.

## ✅ Critérios de aceite

- [ ] Arquivos traduzidos com o mesmo número de frases e tempos dentro da duração original.
- [ ] Nenhum bloco traduzido ultrapassa os limites de caracteres do modo escolhido.

## 🔗 Dependências

Cliente Gemini; agrupamento de blocos (Sprint 1).

<!-- issue: [S6] Sugestão de thumbnail (Gemini com visão) | labels: enhancement, ia, sprint-6 -->
## 🧩 Contexto

O Gemini também entende **imagens**. Dá para extrair vários frames do vídeo e pedir para ele escolher o mais expressivo para a capa.

## 🛠️ O que fazer

1. Extrair ~20 frames candidatos: `ffmpeg -vf "select='gt(scene,0.3)',scale=640:-2" -vsync vfr` (mudanças de cena) ou 1 frame a cada N segundos; descartar frames borrados (variância do Laplaciano com OpenCV, opcional).
2. Enviar as imagens (JPEG, baixa resolução, para economizar tokens) + resumo do vídeo e pedir: `{"best_index": 7, "reason": "...", "suggested_text": "3 ERROS QUE..."}` com as 3 melhores opções.
3. Exportar o frame escolhido **em resolução cheia** como PNG.
4. Opcional: compor uma thumbnail simples com o texto sugerido (Pillow: texto grande com contorno), em 1280×720 ou 1080×1920.
5. **Privacidade**: aqui são enviadas imagens do vídeo para a API. Avisar na interface e documentar no README.

## ✅ Critérios de aceite

- [ ] Retorna 3 opções de frame com o motivo de cada uma.
- [ ] Aviso de privacidade visível antes de enviar as imagens.

## 🔗 Dependências

Cliente Gemini.
