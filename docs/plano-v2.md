# Plano — LegendasAutomáticas v2: cortes virais verificados + legendas com modelos + textos de postagem

> Plano aprovado (backend + frontend). As Sprints estão em `docs/sprints/`.

## Contexto

Hoje o projeto (FastAPI + Celery/Redis + Faster-Whisper `base` + Streamlit) só gera um `.srt` palavra a palavra. O roadmap atual tem 8 Sprints e está num commit local que ainda não foi enviado, porque o GitHub devolveu 403. Nesse roadmap, os cortes virais só aparecem na Sprint 6, e a IA é só o Gemini.

O novo escopo muda o centro do produto:
1. Vídeo longo entra.
2. O sistema gera **cortes virais verificados**, com duração e quantidade escolhidas.
3. Gera **legendas corrigidas com modelos virais** (emojis e destaques).
4. Exporta **SRT para o CapCut** e o **MP4 9:16**.
5. Escreve os **textos de postagem**: TikTok, Shorts, Reels e YouTube longo.

Tudo **local via Docker**, gratuito sempre que possível, usando Qwen (local), Gemini (nível gratuito) e Claude (assinatura). A meta é ser peça de portfólio com caminho para virar SaaS.

**Princípio central: a IA nunca inventa tempo.** Os tempos de corte vêm de sinais medidos localmente. A IA só escolhe IDs, avalia e escreve.

## Decisões (entrevista R1–R7)

| # | Decisão |
|---|---|
| D1 | Frontend em **React + TypeScript** (plano separado) |
| D2 | Claude: **assinatura via `claude -p`** por padrão + chave de API opcional (`CLAUDE_MODE=subscription\|api\|off`) |
| D3 | Só eu, mas **pronto para multiusuário** (login simples, todo dado com `user_id`) |
| D4 | Entrada: **upload + link YouTube/Twitch** (yt-dlp com aviso de direitos autorais) |
| D5–D6 | Usuário escolhe **duração (15/30/60/90 s) + quantidade N**. Duração **±20%**, sempre com frase completa |
| D7 | Saída **9:16 com câmera seguindo o rosto** (opção: manter o original) |
| D8 | **Perfis de conteúdo**: podcast (2+ pessoas), 1 pessoa, live/gameplay, vlog |
| D9 | Gemini **só no nível gratuito** → orçamento diário + reserva local |
| D10 | Juiz multimodal **assiste ao trecho em baixa resolução** |
| D11 | Aprovação por **consenso de 2 juízes de famílias diferentes + validadores de código** |
| D12 | Vídeo de **até 1 h** (configurável) |
| D13 | Hashtags em alta via **Claude Code com busca web**, cache de 24 h por nicho + lista fixa do usuário |
| D14 | Textos para **TikTok, Shorts, Reels e YouTube longo** (este com capítulos) |
| D15 | **PT-BR**, com estrutura pronta para outros idiomas |
| D16 | Emojis e destaques **no SRT e no vídeo com modelo** |
| D17–D18 | **Windows + Docker Desktop (WSL2) com GPU**; Ollama em container |
| D19 | **PostgreSQL** + Alembic |
| D20 | Retenção: **original 7 dias, cortes 30 dias** |
| D21 | Render em dois modos: **prévia NVENC** e **final x264 CRF 17 em 1080x1920** |
| D22 | **Monorepo** `backend/ frontend/ infra/`; Streamlit e `launcher.py` saem |
| D23 | **Tudo em PT-BR** (código, comentários e docs). Docs **curtas e simples**. Inglês fica para o fim do projeto (usuário) |
| D24 | Entrega por **fatia vertical ponta a ponta** primeiro |
| D25 | Diarização com **pyannote** (token gratuito do HuggingFace) |
| D26 | Claude com **teto diário configurável** (padrão 15 chamadas). Ao acabar, usa o Qwen e avisa na tela |
| D27 | Re-gerar: **mais cortes sem repetir, ajuste manual de início/fim, busca por tema, marcar momento favorito** |
| D28 | **Aprender com aprovações e rejeições** (calibra os pesos e vira o conjunto de ouro) |
| D29 | Modos: **palavra por palavra, frase curta (2–4), frase com palavra ativa (karaokê), frase completa (1–2 linhas)** |
| D30 | Cores de destaque **por significado (IA)**: cada modelo tem paleta por categoria (dinheiro, alerta, surpresa, emoção, padrão) |
| D31 | Motor da legenda: **Remotion (React)**, prévia no navegador = vídeo final. Confirmar a licença atual (gratuita para indivíduos e empresas pequenas) |
| D32 | **Editor visual de modelos** + "Meus modelos" |
| D33 | Catálogo v1: **Bold/Hormozi, MrBeast, Karaokê, Caixa, Minimal, Clean, Neon, Gradiente** (8 modelos, cada um em qualquer dos 4 modos) |
| D34 | Animação **padrão do modelo e ajustável**: pop, bounce, slide, fade, typewriter, shake × sutil, normal ou forte |
| D35 | Emoji **junto da palavra + sticker grande em 2–3 momentos-chave** |
| D36 | Extras: **IA sugere o modelo, censura de palavrões (asteriscos + beep opcional), legenda que desvia do rosto, SRT nos vários modos** |
| D37 | Elementos virais: **título-gancho (3 s), barra de progresso, @ do perfil, CTA final** |
| D38 | Fontes: **catálogo OFL (~12) + upload próprio** (validado) |
| D39 | **Alinhamento fino** (torchaudio MMS forced aligner, local) só nos cortes escolhidos |
| D40 | Escolha do modelo numa **galeria com prévia tocando o próprio corte** |

## Arquitetura

### Serviços (`infra/docker-compose.yml`)

| Serviço | Função |
|---|---|
| `api` | FastAPI, autenticação JWT, progresso via SSE (Redis pub/sub) |
| `worker-gpu` | Fila `gpu`, concurrency 1. Imagem CUDA + ffmpeg com NVENC. Whisper, pyannote, prévia NVENC |
| `worker-cpu` | Fila `cpu`, concurrency 2. Cenas, rostos, prosódia, PANNs, x264 final |
| `worker-ai` | Fila `ai`. Python + Node + Claude Code CLI. Chamadas a Gemini e Claude |
| `beat` | Retenção, zerar cotas, atualizar hashtags |
| `redis` | Broker, locks e contadores de cota |
| `postgres` | Banco de dados |
| `ollama` | GPU, `OLLAMA_KEEP_ALIVE=0`, `OLLAMA_MAX_LOADED_MODELS=1` |
| `render` | Fila `render`. Node + Remotion + Chromium + Noto Emoji. Gera a **camada de legenda com transparência** (alfa) |
| `frontend` | Fica para o plano de frontend |

Pontos críticos da infraestrutura:
- **GPU:** `deploy.resources.reservations.devices` (nvidia) + `NVIDIA_DRIVER_CAPABILITIES=compute,video,utility`. Sem o `video`, o NVENC não funciona.
- **Um modelo por vez na GPU:** lock no Redis `gpu:lock`, usado também nas chamadas ao Ollama. Depois de cada uso, liberar a memória (`del model`, `torch.cuda.empty_cache()`). Agrupar todas as chamadas ao Qwen de uma análise para trocar menos de modelo.
- **RAM (o gargalo real com 16 GB):** guia com `.wslconfig` (`memory=12GB`, `swap=8GB`). Volumes Docker nomeados, nunca em `/mnt/c`, que é lento.
- **Claude no container:** `claude setup-token` uma vez no host. O token vai em `CLAUDE_CODE_OAUTH_TOKEN` (segredo).
  - O entrypoint **aborta se `ANTHROPIC_API_KEY` existir com `CLAUDE_MODE=subscription`**, porque senão cobraria a API.
  - O CLI roda com `--allowedTools WebSearch` (sem Bash, Read, Edit ou Write), num diretório vazio, e a transcrição vai delimitada como dado. Isso evita *prompt injection* vindo do próprio vídeo.
- **Segredos** (via `.env` fora do git): `GEMINI_API_KEY`, `HF_TOKEN`, `CLAUDE_CODE_OAUTH_TOKEN`, `ANTHROPIC_API_KEY` (opcional), `JWT_SECRET`, `POSTGRES_PASSWORD`.
- **Armazenamento:** interface `Armazenamento` com implementação `ArmazenamentoLocal` agora e S3 quando virar SaaS.

### Estrutura do backend (identificadores em PT-BR, sem acento)

```
backend/app/
  api/v1/        auth, videos, analises, candidatos, cortes, legendas, postagens, modelos, uso
  nucleo/        config, logger, seguranca, banco, armazenamento
  modelos/       SQLAlchemy
  esquemas/      Pydantic (API e contratos da IA)
  pipeline/      executor.py (idempotente) + etapas/ (ingestao, sinais/*, linha_tempo,
                 candidatos, triagem, juiz, editor, consenso, enquadramento, render,
                 legendas, postagens)
  ia/            roteador.py, provedores/ (ollama, gemini, claude_cli, claude_api),
                 prompts/<tarefa>/v<N>.md, orcamento.py, cache.py
  midia/         ffmpeg, ffprobe, ass, srt, proxy
  workers/       celery_app, filas, beat
backend/alembic/   backend/testes/   backend/avaliacao/
pacotes/modelos-legenda/   # TypeScript: componentes Remotion dos modelos + schema do EspecModelo
                           # (usado pelo frontend na prévia E pelo serviço render: mesmo código, mesmo resultado)
render/                    # serviço Node: recebe job, renderiza camada de legenda com alfa
recursos/fontes/  recursos/emoji/   # fontes OFL + imagens Noto Emoji (licença Apache 2.0)
```

**Reaproveitado do código atual:**
- `app/security/validation.py` e `middleware.py`, corrigindo a mensagem de 500 MB;
- `app/core/logger.py`;
- `app/services/audio_service.py`, com o padrão de `subprocess` em lista;
- configuração do Celery em `app/workers/celery_worker.py`;
- `format_timestamp`, corrigido para arredondar.

### Modelo de dados (toda tabela de domínio tem `user_id`)

| Tabela | O que guarda |
|---|---|
| `usuarios` | Conta e idioma |
| `videos` | Origem, metadados ffprobe, caminhos do original e do proxy, perfil, `expira_em` (7 dias) |
| `analises` | Parâmetros (duração-alvo, N, perfil, pesos), etapa atual, progresso, erro amigável |
| `execucoes_etapa` | Etapa, `hash_entrada`, status, artefatos, métricas. Permite **retomar e pular etapas já feitas** |
| `candidatos` | Início e fim, IDs da frase inicial e final, **variantes de início/fim pré-calculadas**, nota heurística, features |
| `julgamentos` | Juiz, modelo, versão do prompt, notas por critério, motivo, **citações**, `valido` |
| `cortes` | Início e fim ajustados (sempre alinhados à palavra), formato, keyframes da câmera, caminhos da prévia e do final, `expira_em` (30 dias) |
| `documentos_legenda` | `DocumentoLegenda` versionado: palavras com índice (texto, início, fim, categoria de destaque, emoji, censurada), momentos-chave, título-gancho, CTA, posição por bloco, diff de correções |
| `modelos_legenda` | `EspecModelo` em JSON versionado (sistema ou usuário) |
| `fontes` | Fontes do catálogo + enviadas pelo usuário (arquivo validado com fontTools) |
| `exportacoes` | Corte + modelo + versão do documento → caminhos dos SRTs (por modo) e do MP4 final |
| `textos_postagem` | Plataforma, título, descrição, hashtags, tags, capítulos |
| `cache_hashtags` | Nicho, plataforma, hashtags, data da busca |
| `hashtags_usuario` | Lista fixa do usuário |
| `chamadas_ia` | Tarefa, provedor, modelo, tokens, custo, latência, cache, status |
| `feedback` | Corte aprovado ou rejeitado, motivo. Base do aprendizado (D28) |

Os artefatos pesados ficam em disco, em `dados/<usuario>/<video>/`: `transcricao.json`, `features.parquet`, `proxy.mp4`, `audio.wav`. O Celery é só transporte; o estado fica no banco. Isso acaba com o bug do `str(dict)`.

### Pipeline (cada etapa é idempotente: se o `hash_entrada` já foi processado, pula; grava com escrita atômica; publica progresso)

1. **ingestao** (cpu)
   - ffprobe e limite de 1 h;
   - proxy de 480p com keyframe a cada 1 s;
   - `audio.wav` 16k mono;
   - variante yt-dlp, com o aceite do aviso registrado.
2. **sinais** (em paralelo):
   - `asr` (gpu): Whisper `large-v3-turbo` fp16, tempo por palavra, VAD, idioma e vocabulário, + filtro de alucinação (frases fantasmas e repetição).
   - `diarizacao` (gpu, só no perfil podcast): pyannote. Sem token, usa o fallback de movimento de boca.
   - `eventos_audio` (cpu): PANNs CNN14 calcula, por segundo, a probabilidade de risada, aplauso, grito e música.
   - `prosodia` (cpu): librosa mede volume, variação de tom, palavras por segundo e pausas.
   - `cenas` (cpu): PySceneDetect `AdaptiveDetector`.
   - `rostos` (cpu): MediaPipe a 5 fps, com caixas, rastreamento e abertura de boca.
3. **linha_tempo**: junta tudo em `features.parquet` por segundo e calcula o **falante ativo** (abertura de boca × volume + diarização).
4. **candidatos** (só código)
   - janelas que começam e terminam em frase, com duração dentro do alvo ±20%;
   - nota = Σ peso do perfil × sinais (gancho nos 3 s iniciais, picos de energia, risadas, variação de tom, mudança de cena, penalidade por silêncio);
   - remove sobreposições (IoU > 0,3) e fica com `max(4N, 30)`;
   - **3 variantes de início e 3 de fim** por candidato.
5. **triagem** (Qwen 3.5 9B local, temperatura 0,1, JSON schema)
   - rubrica de 0 a 10: gancho em 3 s, entende-se sozinho, desfecho, emoção, clareza e polêmica;
   - lotes de 5 candidatos;
   - devolve só ID, notas e **uma citação literal**;
   - 3 amostras com mediana (barato, porque é local);
   - sobem os top 10.
6. **juiz multimodal**
   - Gemini (3.5 Flash-Lite ou 3.8 Flash) assiste aos clipes em 360p, de 3 a 5 por requisição, cada um com uma etiqueta `ID:c12` gravada na imagem.
   - Se a cota acabar: Gemma 4 E4B local, com frames a cada 2 s + resumo textual dos sinais de áudio. O áudio nativo pelo Ollama é instável.
7. **editor-chefe**: **1 chamada ao Claude por análise**, com JSON compacto do top 10 (texto, sinais, notas dos juízes, variantes). Devolve a ordem, a **variante escolhida (por ID)**, o motivo e o gancho.
8. **consenso**: o corte é aprovado se passar nos validadores e tiver **2 juízes de famílias diferentes** com nota ≥ limiar. Fica pronto para revisão.
9. **revisão humana** (API)
   - ajuste de início e fim, alinhado à palavra mais próxima;
   - "gerar mais" pega os próximos candidatos já analisados;
   - **busca por tema**: o Qwen procura nas frases e o código monta as janelas;
   - **momento favorito**: um clique gera janelas em volta do instante, e elas passam pelo mesmo funil.
10. **enquadramento** (cpu)
    - câmera virtual com alvo no rosto do falante ativo;
    - filtro One-Euro, zona morta e velocidade máxima;
    - reinicia em corte de cena;
    - no podcast, troca de câmera com histerese de 1 s;
    - gera `enquadramento.json` com keyframes.
11. **legendas**: gera o `DocumentoLegenda` (veja a seção "Sistema de modelos de legenda").
12. **render** (sempre a partir do original, em um único encode do vídeo)
    - **Prévia no navegador não usa servidor:** o `@remotion/player` toca o proxy + `DocumentoLegenda` + `EspecModelo`.
    - **Final:**
      1. o serviço `render` (Remotion) gera a **camada de legenda com alfa** (ProRes 4444 ou WebM VP9 com alfa, em 1080x1920);
      2. o ffmpeg (fila cpu) faz numa passada só: original → recorte dinâmico pelo `enquadramento.json` → sobreposição da camada → x264 `-crf 17 -preset slow` + `loudnorm` + beep da censura (opcional).
    - **Prévia rápida em MP4** (opcional): o mesmo processo com `h264_nvenc` em 720x1280.
13. **postagens** (Claude)
    - textos das 4 plataformas;
    - capítulos derivados das fronteiras de tópico e cena (IDs, nunca tempo inventado);
    - hashtags: primeiro o cache de 24 h por nicho; se faltar, `claude -p` com WebSearch; depois junta com a lista fixa.
14. **aprendizado** (beat, semanal): com as aprovações e rejeições, recalibra os pesos de cada perfil (regressão logística simples) e escolhe exemplos para os prompts.

### Sistema de modelos de legenda

**Ideia:** separar **conteúdo** de **aparência**:
- `DocumentoLegenda` diz **o quê** e **quando**;
- `EspecModelo` diz **como fica**;
- o mesmo componente React (Remotion) desenha os dois na prévia e no vídeo final.

**1. Geração do `DocumentoLegenda`** (backend, etapa `legendas`):
1. Palavras do corte (vindas da transcrição) → **alinhamento fino** com o MMS forced aligner (D39) → re-snap dos tempos.
2. Correção pelo Qwen **preservando índices** (regras anti-alucinação 1, 2 e 4).
3. **Enriquecimento pela IA**, numa chamada só ao Qwen por corte, que devolve por índice:
   - `categoria_destaque` (dinheiro, alerta, surpresa, emoção, padrão ou null), no máximo ~15% das palavras;
   - `emoji` (validado como 1 emoji Unicode);
   - os **2–3 momentos-chave** (índices) para o sticker grande;
   - o modelo sugerido para o corte (D36).
   O título-gancho vem do editor-chefe; o CTA vem de um texto padrão do usuário ou da IA.
4. **Censura:** lista PT-BR configurável → `censurada=true` + texto com asterisco (`p*rra`) + intervalos para o beep.
5. **Desvio de rosto:** com as caixas dos rostos (etapa `rostos` + `enquadramento.json`), calcula `posicao_y` por bloco, sempre dentro da **área segura** do TikTok/Reels/Shorts.

**2. Blocos por modo (função pura, igual no TS e no Python, com testes que comparam os dois):**

| Modo | Regra |
|---|---|
| palavra | 1 palavra por bloco, duração mínima de 0,25 s |
| frase curta | 2–4 palavras, ≤ 18 caracteres, quebra em pausa > 0,4 s ou pontuação |
| karaokê | blocos de frase curta/média; a palavra ativa troca pelo tempo dela |
| frase completa | ≤ 42 caracteres por linha, no máximo 2 linhas, ≤ 6 s |

**3. `EspecModelo` (JSON versionado, validado por schema nos dois lados):**
- fonte, peso, tamanho (% da altura), caixa alta;
- cor base;
- **paleta por categoria**;
- contorno, sombra, brilho (neon), gradiente;
- caixa de fundo (cor, raio, padding);
- estilo da palavra ativa (cor, escala, caixa);
- animação de entrada e de destaque (tipo × intensidade);
- emoji (`inline`, `sticker` ou ambos) e tamanho do sticker;
- posição (topo, meio, base, ou automática com desvio de rosto) + margem da área segura;
- densidade de destaque;
- elementos (D37): título-gancho (fonte, cor, duração 3 s), barra de progresso (cor, espessura, posição), @ do perfil (canto, opacidade), CTA (texto, últimos 2 s).

Os **8 modelos de sistema** (D33) são arquivos JSON em `pacotes/modelos-legenda/modelos/`. "Meus modelos" ficam no banco, com o mesmo schema.

**4. Emojis idênticos em qualquer lugar:** o componente desenha o emoji como **imagem Noto** (via `recursos/emoji/`), nunca como fonte do sistema. Assim, a prévia no Windows sai igual ao vídeo final.

**5. Fontes:**
- catálogo OFL em `recursos/fontes/` (Montserrat, Bebas Neue, Anton, Poppins, Inter, Oswald, Archivo Black, Bangers, Luckiest Guy, Rubik, Barlow Condensed, Lilita One);
- upload de `.ttf`/`.otf` validado (extensão, tamanho, `fontTools` abre sem erro), servido para a prévia e para o render.

**6. Exportações:**
- `legenda_<modo>.srt` para os 4 modos, com emojis, destaques em MAIÚSCULAS e censura aplicada;
- MP4 final com o modelo;
- `documento.json`, para reabrir depois.

### Roteador de IA (`ia/roteador.py`)

Fluxo de cada chamada:
1. Resolve a cadeia de provedores da tarefa.
2. Consulta o cache (`sha256(tarefa + versao_prompt + modelo + payload)`).
3. Confere o orçamento.
4. Faz a chamada.
5. Valida (Pydantic + regras de domínio).
6. Se falhar, tenta 1 vez com o erro no prompt e depois passa para o próximo provedor.
7. Registra em `chamadas_ia`.

| Tarefa | Primário | Reserva | Por quê |
|---|---|---|---|
| triagem | Qwen 3.5 9B | só heurística | Muito volume, custo zero |
| juiz multimodal | Gemini Flash-Lite / Flash | Gemma 4 E4B | Único que "assiste"; cota pequena |
| editor-chefe | Claude Sonnet (CLI) | Haiku 5.5 (API) → Qwen | Julgamento final em 1 chamada |
| correção de legenda | Qwen | sem correção | Local, com índices preservados |
| enriquecimento da legenda (categoria de destaque, emoji, momentos-chave, modelo sugerido) | Qwen | dicionário de regras + modelo padrão do perfil | Barato, 1 chamada por corte |
| textos de postagem | Claude (CLI) | Haiku (API) → Qwen | Qualidade de texto |
| hashtags em alta | Claude + WebSearch | cache antigo + lista fixa | Precisa de internet |

**Orçamentos:**
- Gemini: contador diário no Redis por modelo, com RPD configurável e reserva de 20%. Erro 429 vai direto para a reserva.
- Claude: `CLAUDE_CHAMADAS_DIA=15`, com no máximo 1 editor e 1 postagem por análise.
- No modo API: teto diário em US$, cache de prompt e Batch API para as postagens.

**Anti-alucinação:**
1. Só IDs entram e saem (candidato, variante, frase, palavra).
2. JSON schema estrito, rejeitando ID desconhecido ou repetido.
3. Cada citação precisa ser um trecho literal da transcrição; senão o julgamento é inválido.
4. Na correção de legenda, o número de itens é o mesmo, e se a palavra mudar mais de 40% (distância de edição), fica a original.
5. Temperatura entre 0 e 0,2.
6. Consenso de 2 famílias de modelos.
7. Validadores de código: duração na faixa, frase completa, silêncio inicial ≤ 1,5 s, rosto visível em ≥ 60% do tempo (perfis com rosto).
8. Prompts versionados; a versão entra no hash e no julgamento.

### Avaliação (credibilidade de portfólio)

- **Conjunto de ouro:** 8 a 10 vídeos seus, cobrindo os 4 perfis, com de 5 a 10 momentos marcados à mão em cada um. Ele cresce com o feedback (D28).
- **Métricas de cortes:** precision@N e recall@N (acerto quando a sobreposição temporal com um momento marcado é ≥ 0,5), taxa de frase completa e nota cega de 1 a 5.
- **Ablação:** só heurística → + Qwen → + Gemini → + Claude, mostrando o ganho de cada camada.
- **Legendas:** WER e CER (`jiwer`) antes e depois da correção.
- **Operação:** tempo por etapa, chamadas e custo por análise, taxa de uso da reserva.
- `make avaliar` gera um relatório curto. O CI roda um subconjunto em CPU.

## Sprints (substituem as 8 atuais)

| Sprint | Objetivo | Tarefas principais | Pronto quando |
|---|---|---|---|
| **S0 Fundação** | Monorepo + infra | Novo layout; compose com GPU; Postgres + Alembic; JWT + `user_id`; `Armazenamento`; executor idempotente + `execucoes_etapa`; SSE; CI (ruff, pytest); remover Streamlit, launcher e `StaticFiles`; corrigir os bugs conhecidos; guia de `.wslconfig` | `docker compose up` sobe tudo, `nvidia-smi` funciona no worker-gpu, testes verdes |
| **S1 Fatia vertical** | Ponta a ponta mínima | Ingestão + proxy; Whisper turbo + `transcricao.json`; candidatos por frase + nota de energia; triagem Qwen; API da galeria + ajuste de início e fim; render com recorte central; **`DocumentoLegenda` básico + pacote Remotion com 1 modelo (Bold) em modo frase curta + composição ffmpeg**; SRT | Vídeo de 1 h vira N cortes 9:16 com legenda, baixáveis |
| **S2 Sinais e perfis** | Detecção rica | Prosódia, PANNs, cenas, rostos, diarização (+ reserva); `features.parquet`; pesos por perfil; filtro de alucinação do ASR; conjunto de ouro + precision@N + WER | Nota heurística ≥ S1 no conjunto de ouro |
| **S3 Roteador e juízes** | IA confiável | Provedores, cache, orçamentos, prompts versionados; juiz Gemini com reserva Gemma; editor Claude (cli, api, off); validadores + consenso; `chamadas_ia` | Ablação registrada; cota esgotada não quebra nada |
| **S4 Câmera virtual** | Enquadramento | Rastreamento + One-Euro; falante ativo; troca de câmera no podcast; modo original | Sem tremedeira; troca certa em ≥ 85% dos casos de teste |
| **S5a Legendas: texto** | Precisão + inteligência | Alinhamento fino (MMS); correção com índices; 4 modos de blocos (TS e Python iguais); enriquecimento por IA (categoria, emoji, momentos-chave, modelo sugerido); censura + beep; desvio de rosto/área segura; SRT nos 4 modos | WER depois ≤ WER do Whisper; erro de sincronia mediano < 80 ms; SRT abre no CapCut |
| **S5b Legendas: modelos** | Visual viral | Schema `EspecModelo`; 8 modelos de sistema; animações × intensidade; paleta por categoria; emoji Noto inline + sticker; elementos virais (gancho, barra, @, CTA); fontes OFL + upload; API de "Meus modelos" | Os 8 modelos × 4 modos renderizam igual na prévia e no MP4 (teste de comparação de frames) |
| **S6 Postagens + URL + re-gerar** | Publicação e controle | Textos das 4 plataformas; capítulos; hashtags (cache + lista); yt-dlp com aviso; gerar mais, busca por tema, momento favorito | Textos válidos; hashtags com até 24 h |
| **S7 Endurecimento + aprendizado** | Pronto para SaaS | Retenção (beat); aprendizado de pesos; cotas por usuário; rate limit; MIME real/ffprobe no upload; observabilidade; docs curtas | Checklist de segurança ok; relatório de avaliação |

**Vai para o backlog:** remoção de silêncios e vícios de fala com remapeamento, redução de ruído, música e zoom, tradução e thumbnail. O `loudnorm` continua no render.
**Descartado:** wizard em Streamlit, correção do launcher e o SRT com um bloco por palavra.

**Formato das Sprints em `docs/sprints/`:** as tarefas terão objetivo, checklist e critério de aceite, sem textos longos (D23). O script `scripts/sincronizar_github.py` (Action) cria e organiza tudo.

## Riscos (inclui os do sistema de legendas)

- **Remotion:** renderiza via Chromium e é mais pesado em RAM e CPU. Só a camada de legenda passa pelo Remotion, com concurrency 1 a 2. Estimativa: 30–90 s por corte de 60 s. Confirmar os termos da licença antes de virar SaaS.
- **Prévia igual ao final:** a prévia e o render usam o mesmo pacote, os mesmos emojis em imagem e as mesmas fontes. Um teste automatizado compara frames da prévia com frames do render.

- **VRAM e RAM:** um modelo por vez com o lock. Cada troca de modelo custa de 5 a 15 s. `num_ctx` ≤ 8k no Qwen. `.wslconfig` é obrigatório.
- **Tempo estimado para 1 h de vídeo até a galeria: ~20 a 35 min.** Por corte de 60 s: prévia em 10 a 20 s e final em 1 a 3 min.
- **Gemini gratuito:** limites instáveis, ~3 a 5 análises por dia. A reserva Gemma é obrigatória. No nível gratuito, o Google pode usar os dados (para SaaS, trocar de nível via `GEMINI_NIVEL`).
- **Claude:** o uso da assinatura é pessoal. Para vender, `CLAUDE_MODE=api`. O pipeline precisa funcionar com `off`. O CLI fica isolado num adaptador com teste de contrato.
- **pyannote:** modelo restrito. Baixar em tempo de execução, nunca dentro da imagem.
- **yt-dlp:** viola os termos do YouTube e da Twitch fora de uso pessoal com conteúdo próprio ou autorizado. No SaaS, fica atrás de uma flag desligada por padrão.

## Verificação (como provar que funciona)

1. `docker compose up` e `docker compose exec worker-gpu nvidia-smi` (GPU visível; `ffmpeg -encoders | grep nvenc`).
2. `pytest` (unitários: validadores, snap de frase, roteador com provedores mockados, orçamento; integração: pipeline com um vídeo de 2 min em CPU).
3. Fatia vertical manual: subir um vídeo de 10 min, escolher 30 s × 3 e conferir a galeria com nota e motivo, ajustar o início, renderizar, baixar o SRT, importar no CapCut e conferir a sincronia.
4. Teste de queda: zerar a cota do Gemini e usar `CLAUDE_MODE=off`. O pipeline precisa completar usando as reservas.
5. `make avaliar` no conjunto de ouro: precision@N, WER e relatório de ablação.
6. Legendas:
   - renderizar os 8 modelos × 4 modos de um corte de teste;
   - comparar frames da prévia (Player) com o MP4 final;
   - conferir emoji colorido, destaque por categoria, palavrão censurado com beep e legenda fora do rosto;
   - importar os 4 SRTs no CapCut.

## Frontend

### Decisões (entrevista F1–F3)

| # | Decisão |
|---|---|
| F1 | Visual **escuro estilo editor de vídeo** (CapCut/Submagic), cor de destaque vibrante, opção de tema claro |
| F2 | **Desktop primeiro.** No celular: acompanhar progresso, ver cortes, baixar e copiar textos |
| F3 | Linha do tempo com **alças com ímã, forma de onda, mapa de calor dos sinais e palavras da legenda na trilha** |
| F4 | Progresso com **etapas ao vivo + tempo estimado + notificação do navegador**. Pode fechar a aba |
| F5 | Card de corte com **prévia em loop no hover, nota por critério + concordância dos juízes, motivo + título-gancho, 👍/👎 com motivo** |
| F6 | **Painel de cotas de IA, saúde do sistema e configurações pela tela** (segredos criptografados) |
| F7 | **Atalhos de teclado, desfazer/refazer, salvamento automático, exportação em lote** |
| F8 | Textos de postagem em **abas por plataforma**, editáveis, com contador e limite, hashtags como etiquetas, copiar e "regerar com outro tom" |
| F9 | **Assistente de primeiro uso** (GPU, modelos Ollama, tokens, criar usuário) |
| F10 | Biblioteca em **lista com busca e filtros** (miniatura, duração, status, aprovados, dias até expirar) |

### Stack (decidida pelos critérios de portfólio, simplicidade e rodar local)

- **Vite + React + TypeScript** (SPA servida por nginx no container `frontend`; SSR não é necessário);
- **Tailwind + shadcn/ui** + lucide (ícones);
- **TanStack Query** (dados da API) + **Zustand** (estado do editor, com pilha de desfazer/refazer);
- **React Router**;
- **react-i18next** (PT-BR, i18n-ready, D15);
- **@remotion/player** + pacote `pacotes/modelos-legenda` (prévia idêntica ao final, D31);
- **wavesurfer.js** (forma de onda, com picos pré-calculados no backend);
- linha do tempo própria em canvas (trilhas: sinais, palavras, alças);
- **Zod** para validar os contratos;
- tipos gerados do OpenAPI do FastAPI (`openapi-typescript`), para manter um contrato único.

Testes: **Vitest** + Testing Library (componentes e lógica de blocos) e **Playwright** (fluxo ponta a ponta).

### Telas e rotas

| Rota | Tela | Conteúdo principal |
|---|---|---|
| `/primeiro-uso` | Assistente | Teste de GPU → `ollama pull` com barra → validar o token do Claude, a chave do Gemini e o HF token → criar usuário |
| `/entrar` | Login | E-mail e senha (JWT em cookie httpOnly) |
| `/` | Biblioteca | Lista + busca + filtros. Botão "Novo vídeo" |
| `/novo` | Enviar | Upload com arrastar e soltar (com progresso e retomada) **ou** link YouTube/Twitch + aceite de direitos. Perfil, duração (15/30/60/90), quantidade N, vocabulário |
| `/videos/:id` | Análise | Etapas ao vivo (SSE) com tempo estimado; notificação ao terminar; erro amigável com "tentar de novo a partir desta etapa" |
| `/videos/:id/cortes` | Galeria | Cards (F5); ordenar por nota; "gerar mais", "buscar por tema", "momento favorito" (abre o player do vídeo inteiro com mapa de calor); seleção múltipla para exportação em lote |
| `/cortes/:id` | **Editor do corte** | Player 9:16 (Remotion) · linha do tempo (F3) · painel lateral com abas: **Modelo** (galeria tocando o próprio corte, D40), **Legenda** (texto, destaque, emoji, censura por palavra), **Enquadramento** (9:16 automático/manual, original), **Elementos** (gancho, barra, @, CTA) |
| `/modelos` e `/modelos/:id` | Editor de modelos | Controles do `EspecModelo` (fonte, cores por categoria, contorno, caixa, animação × intensidade, posição, emoji, elementos) com prévia ao vivo num corte de exemplo; duplicar a partir dos 8 modelos de sistema; upload de fonte |
| `/cortes/:id/exportar` | Exportar e postar | Render final com progresso; downloads (MP4, os SRTs dos 4 modos, `documento.json`); **abas de postagem** (F8) |
| `/painel` | Painel | Cotas (Gemini e Claude hoje, uso local), histórico de `chamadas_ia`, saúde (GPU, Ollama, tokens, disco) com "como resolver" |
| `/config` | Configurações | Chaves, tetos diários, perfil padrão, @, CTA padrão, hashtags fixas, censura (lista), retenção |

**Celular:** biblioteca, análise, galeria (prévia, 👍/👎, baixar) e abas de postagem (copiar). Editor e modelos aparecem como "abra no computador".

### Editor do corte (peça central)

- **Linha do tempo** (canvas, zoom de 1 s a 5 min, com rolagem):
  - trilha de vídeo com miniaturas;
  - forma de onda;
  - **mapa de calor** (energia, risadas, cenas, falante ativo, tudo vindo do `features.parquet` reduzido);
  - trilha de **palavras** (bloquinhos, clique para editar, arrastar borda para ajustar o tempo, alinhado ao vizinho);
  - **alças de início e fim** com ímã nas fronteiras de palavra e frase. Os cálculos de alinhamento são os mesmos do backend; o servidor revalida.
- **Atalhos:** Espaço play · I/O início/fim · J/K/L · ←/→ palavra anterior/seguinte · Ctrl+Z / Ctrl+Shift+Z · Ctrl+S (força salvar).
- **Desfazer/refazer:** pilha de comandos no Zustand (sem gravar snapshots inteiros).
- **Salvamento automático:** debounce de 1 s → `PATCH` com versão (lock otimista; se der conflito, avisa). Cada salvamento cria uma nova versão do `DocumentoLegenda` e do corte.
- **Galeria de modelos no editor:** 8 cards com prévia **ao passar o mouse**. Para preservar o desempenho, só toca um Player por vez; os outros mostram uma miniatura animada gerada pelo próprio Player.

### Endpoints novos que o frontend exige (entram no backend)

- `GET /analises/:id/eventos` (SSE): etapa, progresso, ETA, erro.
- `GET /videos/:id/forma-onda` (picos pré-calculados no ingest) e `GET /videos/:id/mapa-calor?res=1s` (features reduzidas).
- `GET /videos/:id/miniaturas` (sprite de miniaturas gerado no ingest).
- `PATCH /cortes/:id` e `PATCH /documentos-legenda/:id` com `versao` (lock otimista).
- `POST /cortes/exportar-lote`, `POST /cortes/:id/feedback`.
- `POST /analises/:id/mais`, `POST /analises/:id/buscar-tema`, `POST /analises/:id/momento`.
- `GET/POST /modelos`, `POST /fontes` (upload).
- `GET /saude`, `GET /uso-ia`, `GET/PUT /config` (segredos criptografados com Fernet; a chave mestra fica no `.env`).
- `POST /primeiro-uso/*` (teste de GPU, `ollama pull` com progresso via SSE, validação de tokens).
- **Upload retomável** (protocolo tus ou envio em partes) para vídeos de 1–4 GB.

### Frontend nas Sprints

| Sprint | Frontend |
|---|---|
| S0 | Monorepo `frontend/` (Vite, Tailwind, shadcn, Router, Query, i18n), tema escuro/claro, login, layout, cliente com tipos gerados do OpenAPI, Vitest + Playwright no CI |
| S1 | Enviar (upload retomável), Análise (SSE + notificação), Galeria básica, Editor mínimo (Player Remotion + alças de início/fim), Exportar (MP4 + SRT) |
| S2 | Forma de onda + mapa de calor + miniaturas na linha do tempo; seletor de perfil |
| S3 | Cards completos (notas por critério, concordância, motivo, 👍/👎); Painel de cotas de IA |
| S4 | Aba Enquadramento (automático/manual, original) |
| S5a | Trilha de palavras editável, destaque/emoji/censura por palavra, SRT nos 4 modos |
| S5b | Galeria de modelos no editor, editor de modelos `/modelos`, upload de fonte, aba Elementos |
| S6 | Abas de postagem, link YouTube/Twitch, "gerar mais", "buscar por tema", "momento favorito", exportação em lote |
| S7 | Assistente de primeiro uso, Saúde, Configurações pela tela, atalhos + desfazer/refazer finalizados, layout para celular, acessibilidade básica |

### Verificação do frontend

1. `npm run test` (Vitest): blocos por modo (comparados aos do Python), ímã das alças, pilha de desfazer, validação Zod.
2. Playwright ponta a ponta com backend real e um vídeo de 2 min: enviar → acompanhar → galeria → ajustar início → trocar o modelo → exportar → baixar SRT → copiar texto do TikTok.
3. Teste visual: frames do Player comparados aos do MP4 final (mesmo teste do backend).
4. Lighthouse no celular para a biblioteca e a galeria; navegação só por teclado no editor.

## Execução após aprovar o frontend

1. Reescrever `docs/sprints/` (no formato curto da D23):
   - `00-roadmap.md`: visão, arquitetura, decisões D1–D40 e F1–F10;
   - `sprint-0.md` até `sprint-7.md`, incluindo S5a e S5b. Cada tarefa tem objetivo, checklist e critério de aceite;
   - `backlog.md`.
2. Sincronização via `scripts/sincronizar_github.py` (Action).
3. Rodar `--dry-run`, fazer o commit no branch `claude/happy-franklin-cswtxh` e tentar o push. Se der 403 de novo, avisar.
4. Se o acesso ao GitHub voltar, criar as issues.
