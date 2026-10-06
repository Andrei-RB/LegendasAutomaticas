<!-- roadmap: 🗺️ Roadmap: de gerador de legendas para editor de vídeo com IA | labels: roadmap -->
## 🎯 Objetivo

Evoluir o **LegendasAutomáticas** de um gerador simples de `.srt` para um **editor de vídeo com IA**, capaz de:

- Gerar legendas **muito mais precisas** (menos palavras erradas);
- Entregar legendas **estilizadas** (emojis, destaques, temas tipo "Hormozi", karaokê);
- **Editar o vídeo automaticamente**: remover silêncios e vícios de fala, melhorar o áudio, converter para vertical;
- Usar **IA avançada (Gemini)** para revisar o texto, sugerir cortes virais, títulos, hashtags e traduções.

## 🧱 Arquitetura alvo

```
Streamlit (opções do usuário)
        │  POST /upload-video  (arquivo + options JSON)
        ▼
FastAPI ──► Redis ──► Celery Worker (pipeline em etapas)
                         1. FFmpeg: extrai áudio (WAV 16kHz mono)
                         2. Whisper: transcrição com tempo por palavra ──► transcript.json (fonte única da verdade)
                         3. Gemini: revisão + emojis + destaques (opcional)
                         4. Cortes: silêncios / vícios de fala (opcional) + remapeamento dos tempos
                         5. Áudio: ruído / loudness / música (opcional)
                         6. Geradores: .srt / .ass / vídeo final com legenda gravada
                         7. IA extra: cortes virais, título, hashtags, tradução (opcional)
```

**Princípio central:** tudo passa por um `transcript.json` (palavras + tempos + metadados). Todos os geradores (SRT, ASS, cortes, tradução) leem dele. Isso evita retrabalho e permite editar a legenda antes de exportar.

## 📅 Sprints

| Sprint | Tema | Resultado visível para o usuário |
|---|---|---|
| **0** | Fundação e correções | App estável, sem bugs conhecidos, com testes e CI, pronto para receber opções |
| **1** | Precisão da transcrição | Legendas com muito menos erros e blocos de 2–3 palavras |
| **2** | Integração com Gemini | Legenda revisada por IA, com emojis 🔥 e palavras-chave em destaque |
| **3** | Modelos de legenda (.ass) | Temas prontos + download do vídeo com a legenda já gravada |
| **4** | Editor: cortes inteligentes | Remoção automática de silêncios e vícios de fala |
| **5** | Áudio e formato | Áudio limpo, volume padrão das redes, música com ducking, vertical 9:16, zoom |
| **6** | IA avançada | Cortes virais, título/descrição/hashtags, capítulos, tradução, thumbnail |
| **7** | Interface e infraestrutura | Editor de legenda no navegador, histórico, Docker Compose |

Cada Sprint é um **Épico** (issue com label `epic`) e as tarefas dela aparecem como **sub-issues**. Ordem recomendada: 0 → 1 → 2 → 3 → 4. Depois da 4, as Sprints 5, 6 e 7 podem ser feitas em qualquer ordem.

## 🏷️ Convenções

- Labels: `sprint-N`, `epic`, `bug`, `enhancement`, `ia`, `legendas`, `editor`, `audio`, `frontend`, `infra`, `testes`, `docs`.
- Cada tarefa tem: **Contexto → O que fazer → Arquivos afetados → Exemplo de código → Critérios de aceite → Como testar → Dependências**.
- Um branch/PR por tarefa (ex.: `feat/s1-modelo-configuravel`), com `Closes #N` na descrição do PR.
- Toda feature nova deve ser **opcional** (ligada/desligada por uma opção do job) e ter pelo menos um teste automatizado.
- Nenhuma chave de API no código: tudo via `.env` (que nunca vai para o Git).
