<!-- roadmap: 🗺️ Roadmap v2: cortes virais verificados + legendas com modelos + textos de postagem | labels: roadmap -->
## Objetivo

Transformar o projeto num estúdio local (Docker) que:
1. recebe um vídeo longo (upload ou link);
2. encontra **cortes virais verificados**, com duração 15/30/60/90 s e quantidade escolhidas;
3. gera **legendas corrigidas com modelos virais** (cores por significado, emojis, animações);
4. exporta **MP4 9:16** e **SRT para o CapCut**;
5. escreve os **textos de postagem** (TikTok, Shorts, Reels, YouTube).

Tudo gratuito sempre que possível, com Qwen (local), Gemini (nível gratuito) e Claude (assinatura).

## Princípio central

**A IA nunca inventa tempo.** Os tempos vêm de sinais medidos localmente. A IA só escolhe IDs, avalia e escreve.

## Arquitetura

```
React (Vite) ──► FastAPI ──► Redis/Celery ──► workers: gpu | cpu | ai | render(Remotion)
                    │                              │
                PostgreSQL                    Ollama (Qwen/Gemma)
```

**Funil dos cortes:**
1. Sinais locais: transcrição, risadas, entonação, cenas, rostos, quem fala.
2. Candidatos alinhados a frases.
3. Triagem (Qwen).
4. Juiz que assiste ao vídeo (Gemini, ou Gemma como reserva).
5. Editor-chefe (Claude).
6. Consenso de 2 juízes + validadores de código.
7. Revisão humana.

## Decisões principais

| Tema | Decisão |
|---|---|
| Interface | React + TypeScript, tema escuro, desktop primeiro |
| IA | Qwen local · Gemini só no nível gratuito · Claude pela assinatura (`claude -p`) com teto diário, API opcional |
| Infra | Windows + Docker Desktop (WSL2) com GPU · PostgreSQL · Ollama em container |
| Cortes | 15/30/60/90 s ±20%, frase completa, 9:16 seguindo o rosto, 4 perfis de conteúdo |
| Legendas | 4 modos, 8 modelos, editor visual, Remotion (prévia = vídeo final) |
| Idioma | Tudo em PT-BR (código e docs). Docs curtas |

O plano completo, com as decisões D1–D40 e F1–F10, está em `docs/plano-v2.md`.

## Sprints

| Sprint | Entrega |
|---|---|
| S0 | Fundação: monorepo, Docker com GPU, banco, login, CI |
| S1 | Fatia vertical: vídeo → cortes → legenda → MP4 + SRT |
| S2 | Sinais ricos e perfis + conjunto de ouro |
| S3 | Roteador de IA, juízes e consenso |
| S4 | Câmera virtual (seguir o rosto e quem fala) |
| S5a | Legendas: precisão e inteligência |
| S5b | Legendas: modelos virais e editor |
| S6 | Postagens, link do YouTube, re-gerar cortes |
| S7 | Endurecimento, aprendizado e primeiro uso |
| Backlog | Ideias para depois |

## Convenções

- Uma tarefa por PR, com `Closes #N`.
- Toda feature tem teste.
- Nenhum segredo no código.
- Labels: `sprint-N`, `epic`, `backend`, `frontend`, `ia`, `legendas`, `cortes`, `render`, `infra`, `testes`, `docs`.
