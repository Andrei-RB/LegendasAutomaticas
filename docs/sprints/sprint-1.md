<!-- epic: 🎯 Sprint 1 — Precisão da transcrição | labels: epic, sprint-1 -->
## 🎯 Objetivo da Sprint

Reduzir **drasticamente** as palavras erradas nas legendas e deixar a leitura mais agradável, sem usar IA paga. É o maior ganho de qualidade por esforço do projeto inteiro.

## 📊 Como medir o sucesso

Antes de mexer em qualquer coisa, criar o **benchmark de precisão** (tarefa abaixo) e medir o **WER** (Word Error Rate, ou taxa de erro de palavras) do modelo atual (`base`). Meta da Sprint: **reduzir o WER em pelo menos 50%** nos vídeos de teste.

> Exemplo: se de 100 palavras o sistema erra 20 (WER 20%), a meta é errar no máximo 10 (WER 10%).

## ✅ Definição de pronto (DoD)

- [ ] Benchmark com pelo menos 3 vídeos reais e as transcrições corretas.
- [ ] Modelo, idioma e dispositivo configuráveis pelo `.env`.
- [ ] Vocabulário personalizado funcionando.
- [ ] Modos de legenda: palavra a palavra, curto (2–3 palavras) e frase.
- [ ] Alucinações conhecidas do Whisper filtradas.
- [ ] Tabela de resultados (WER × tempo de processamento) documentada no README.

## 📋 Tarefas

As tarefas estão listadas como sub-issues abaixo.

<!-- issue: [S1] Benchmark de precisão (WER) com vídeos de referência | labels: testes, legendas, sprint-1 -->
## 🧩 Contexto

"Está errando palavras" é subjetivo. Para saber se uma mudança **melhorou de verdade**, precisamos de um número. O padrão da área é o **WER (Word Error Rate)**: a porcentagem de palavras trocadas, faltando ou sobrando em relação a uma transcrição correta feita por humano.

## 🛠️ O que fazer

1. Criar `benchmarks/`:
   ```
   benchmarks/
     dados/              # NÃO versionar os vídeos (adicionar ao .gitignore)
       video1.mp4
       video1.txt        # transcrição 100% correta, digitada/revisada à mão
     resultados/         # CSVs gerados
     run_benchmark.py
   ```
2. Escolher 3 a 5 vídeos **seus**, de 1 a 3 min, variados: fala rápida, com música de fundo, com termos técnicos/nomes próprios.
3. O script `run_benchmark.py`:
   - roda a transcrição com uma configuração (modelo, beam_size, vocabulário...);
   - normaliza o texto (minúsculas, sem pontuação) dos dois lados;
   - calcula o WER com a biblioteca `jiwer`;
   - mede o tempo de processamento;
   - salva uma linha em `resultados/AAAA-MM-DD.csv`.
4. Permitir comparar várias configurações de uma vez: `python benchmarks/run_benchmark.py --models base small large-v3-turbo`.

## 💡 Exemplo de código

```python
import jiwer, re, time

def normalizar(t: str) -> str:
    t = t.lower()
    t = re.sub(r"[^\w\sà-ú]", " ", t)
    return " ".join(t.split())

inicio = time.time()
palavras = transcrever(video, modelo=modelo)          # usa a etapa transcribe do pipeline
hipotese = " ".join(w.text for w in palavras)
wer = jiwer.wer(normalizar(referencia), normalizar(hipotese))
print(f"{modelo}: WER={wer:.1%}  tempo={time.time() - inicio:.0f}s")
```

## ✅ Critérios de aceite

- [ ] Rodar o script gera uma tabela comparando as configurações.
- [ ] WER do modelo atual (`base`) registrado como **linha de base** no README.
- [ ] Vídeos de benchmark fora do Git.

## 🔗 Dependências

Pipeline da Sprint 0 (a etapa `transcribe` precisa devolver as palavras sem escrever o SRT).

<!-- issue: [S1] Modelo Whisper configurável (large-v3-turbo) + detecção automática de GPU | labels: enhancement, legendas, sprint-1 -->
## 🧩 Contexto

Hoje o modelo está fixo no código: `WhisperModel("base", device="cpu", compute_type="int8")`. O `base` é pequeno (74M parâmetros) e erra bastante em português. Modelos maiores erram muito menos:

| Modelo | Tamanho | Precisão | Velocidade na CPU |
|---|---|---|---|
| `base` | 74M | ⭐⭐ | rápida |
| `small` | 244M | ⭐⭐⭐ | média |
| `medium` | 769M | ⭐⭐⭐⭐ | lenta |
| `large-v3-turbo` | 809M | ⭐⭐⭐⭐⭐ | lenta na CPU, **rápida na GPU** |
| `large-v3` | 1.55B | ⭐⭐⭐⭐⭐ | muito lenta na CPU |

## 🛠️ O que fazer

1. Novas configurações no `.env` / `config.py`:
   ```
   WHISPER_MODEL=large-v3-turbo
   WHISPER_DEVICE=auto          # auto | cpu | cuda
   WHISPER_COMPUTE_TYPE=auto    # auto | int8 | int8_float16 | float16
   WHISPER_CPU_THREADS=0        # 0 = automático
   WHISPER_MODELS_DIR=models    # onde baixar os modelos (adicionar ao .gitignore)
   ```
2. `device=auto`: usar `cuda` se `ctranslate2.get_cuda_device_count() > 0`, senão `cpu`.
3. `compute_type=auto`: `float16` na GPU e `int8` na CPU.
4. Logar na inicialização do worker qual modelo/dispositivo está em uso.
5. **Pré-carregar** o modelo quando o worker inicia (sinal `worker_process_init` do Celery), para o primeiro job não demorar mais.
6. Script `scripts/baixar_modelo.py` para baixar o modelo antes (o download do `large-v3-turbo` tem ~1,6 GB).
7. Rodar o benchmark com `base`, `small` e `large-v3-turbo` e documentar o resultado.
8. Atualizar o `.env.example` e o README (seção "Escolhendo o modelo" + requisitos de GPU: drivers NVIDIA, CUDA 12 e cuDNN 9).

## 💡 Exemplo de código

```python
import ctranslate2

def resolver_dispositivo():
    device = settings.WHISPER_DEVICE
    if device == "auto":
        device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
    compute = settings.WHISPER_COMPUTE_TYPE
    if compute == "auto":
        compute = "float16" if device == "cuda" else "int8"
    return device, compute

device, compute = resolver_dispositivo()
model = WhisperModel(settings.WHISPER_MODEL, device=device, compute_type=compute,
                     download_root=settings.WHISPER_MODELS_DIR, cpu_threads=settings.WHISPER_CPU_THREADS)
```

## ✅ Critérios de aceite

- [ ] Trocar o modelo exige só alterar o `.env`.
- [ ] Com GPU NVIDIA, usa CUDA automaticamente; sem GPU, CPU com int8.
- [ ] WER do `large-v3-turbo` medido e menor que o do `base`.
- [ ] O primeiro job não paga o tempo de carregamento do modelo.

## 🔗 Dependências

Benchmark de precisão (para medir).

<!-- issue: [S1] Idioma configurável + parâmetros de decodificação anti-erro | labels: enhancement, legendas, sprint-1 -->
## 🧩 Contexto

Hoje a transcrição chama `transcribe(audio_path, vad_filter=True, word_timestamps=True)` sem idioma. O Whisper **adivinha o idioma** pelos primeiros 30 s. Se o vídeo começa com música ou com uma palavra em inglês, ele pode transcrever tudo errado ou até traduzir. Os parâmetros de decodificação também estão no padrão.

## 🛠️ O que fazer

1. Usar `JobOptions.language` (padrão `"pt"`). Aceitar `"auto"` para detecção automática.
2. Ajustar os parâmetros (validar cada um no benchmark):

| Parâmetro | Valor sugerido | Por quê |
|---|---|---|
| `language` | `"pt"` | Evita detecção errada |
| `beam_size` | `5` | Busca mais alternativas, mais precisa |
| `best_of` | `5` | Idem, para os fallbacks de temperatura |
| `temperature` | `[0.0, 0.2, 0.4, 0.6, 0.8, 1.0]` | Tenta de novo, com mais "criatividade", quando a confiança é baixa |
| `condition_on_previous_text` | `False` | Evita **loops de repetição** (a mesma frase repetida várias vezes) |
| `vad_filter` | `True` | Ignora silêncio e ruído |
| `vad_parameters` | `{"min_silence_duration_ms": 500, "speech_pad_ms": 200}` | Não corta o começo/fim das palavras |
| `no_speech_threshold` | `0.6` | Descarta trechos sem fala |
| `compression_ratio_threshold` | `2.4` | Detecta texto repetitivo (alucinação) |

3. Expor os parâmetros avançados no `.env` (com os valores acima como padrão).
4. Seletor de idioma no frontend: Português, Inglês, Espanhol, Automático.

## ✅ Critérios de aceite

- [ ] Vídeo em português que começa com música é transcrito em português.
- [ ] Nenhum loop de repetição nos vídeos de benchmark.
- [ ] WER igual ou menor que a configuração anterior.

## 🔗 Dependências

Benchmark de precisão.

<!-- issue: [S1] Vocabulário personalizado (nomes, marcas, gírias) | labels: enhancement, legendas, sprint-1 -->
## 🧩 Contexto

O Whisper erra muito em **nomes próprios, marcas e termos do nicho**: "CapCut" vira "capicute", "Andrei" vira "Andrey", "Shorts" vira "shortes". O faster-whisper permite "dar dicas" ao modelo com `initial_prompt` e `hotwords`.

## 🛠️ O que fazer

1. `JobOptions.vocabulary: list[str]` (máximo de ~50 termos, cada um com até 40 caracteres).
2. Vocabulário global no `.env`: `DEFAULT_VOCABULARY="CapCut,Shorts,Reels,TikTok"`.
3. Montar o prompt: `initial_prompt = "Vocabulário: CapCut, Shorts, Andrei. "` + uma frase de estilo com pontuação ("Olá, tudo bem? Hoje vamos falar sobre...") para incentivar a pontuação correta.
4. Passar também `hotwords=" ".join(vocabulary)`, que está disponível no faster-whisper >= 1.0.
5. **Pós-correção determinística**: depois da transcrição, comparar cada palavra com o vocabulário por similaridade (`rapidfuzz`, score >= 85) e trocar. Exemplo: "capicute" → "CapCut".
6. Frontend: campo de texto "Palavras que aparecem no vídeo (separadas por vírgula)", lembrado entre usos.
7. Sanitizar as entradas (remover quebras de linha, limitar o tamanho).

## 💡 Exemplo de código

```python
from rapidfuzz import process, fuzz

def corrigir_com_vocabulario(palavras, vocabulario):
    for w in palavras:
        limpo = w.text.strip(".,!?").lower()
        match = process.extractOne(limpo, vocabulario, scorer=fuzz.ratio, score_cutoff=85)
        if match:
            w.text = w.text.lower().replace(limpo, match[0])
    return palavras
```

## ✅ Critérios de aceite

- [ ] Um vídeo que fala "CapCut" sai com "CapCut" quando o termo está no vocabulário.
- [ ] Sem vocabulário, o comportamento é igual ao anterior.
- [ ] Teste unitário da pós-correção (inclusive para **não** trocar palavras comuns parecidas).

## 🔗 Dependências

Pipeline da Sprint 0.

<!-- issue: [S1] Agrupar palavras em blocos de legenda (palavra / curto / frase) | labels: enhancement, legendas, sprint-1 -->
## 🧩 Contexto

Hoje **cada palavra vira um bloco** do SRT. Em vídeos rápidos isso fica cansativo: a legenda "pisca" demais e, no CapCut, gera centenas de blocos para ajustar. O padrão dos criadores é **2 a 3 palavras por vez** (Reels/Shorts) ou **frases curtas** (YouTube).

## 🛠️ O que fazer

1. Criar `app/captions/grouping.py` com `agrupar(words, modo, max_palavras, max_caracteres, max_duracao)`.
2. Modos (`JobOptions.caption_mode`):
   - `word`: 1 palavra por bloco (comportamento atual);
   - `short`: até `max_words_per_caption` (padrão 3) palavras, no máximo ~16 caracteres;
   - `sentence`: até 42 caracteres por linha, no máximo 2 linhas, no máximo 6 s.
3. Regras de quebra (fecham o bloco atual):
   - atingiu o máximo de palavras ou caracteres;
   - pausa maior que 0,4 s entre duas palavras;
   - a palavra termina com pontuação forte (`.`, `!`, `?`). Vírgula conta só no modo `sentence`;
   - duração passou do máximo.
4. Evitar "viúvas": um bloco com só 1 palavra curta no fim de frase é juntado ao anterior quando possível.
5. Cada bloco guarda os índices das palavras (`word_range`), o que é essencial para o karaokê/destaque da Sprint 3.
6. O gerador SRT passa a usar os blocos.
7. Frontend: seletor "Estilo de legenda: Palavra a palavra / 2–3 palavras / Frases".

## 💡 Exemplo de saída (modo `short`)

```
1
00:00:00,520 --> 00:00:01,100
Hoje vou ensinar

2
00:00:01,100 --> 00:00:01,900
como ganhar dinheiro
```

## ✅ Critérios de aceite

- [ ] Os três modos funcionam e são testados com um transcript fixo.
- [ ] Nenhum bloco ultrapassa os limites configurados.
- [ ] Pausas longas sempre quebram o bloco.
- [ ] Importar o SRT no CapCut mostra os blocos corretamente.

## 🔗 Dependências

Pipeline da Sprint 0.

<!-- issue: [S1] Ajustes de tempo e filtro de alucinações do Whisper | labels: enhancement, legendas, sprint-1 -->
## 🧩 Contexto

Problemas comuns de legenda automática que dá para corrigir com regras simples:

1. **Alucinações conhecidas do Whisper em PT-BR**: frases que aparecem em trechos de silêncio ou música, como "Legendas pela comunidade Amara.org", "Obrigado por assistir", "Inscreva-se no canal", "Legenda Adriana Zanotto".
2. **Legendas piscando**: palavras com duração de 0,05 s somem antes de dar para ler.
3. **Sobreposição**: o fim de um bloco depois do início do próximo, o que gera um erro visual no CapCut.
4. **Palavras com confiança muito baixa** (`probability < 0.3`), normalmente lixo ou ruído.

## 🛠️ O que fazer

Criar `app/captions/cleanup.py`, aplicado depois da transcrição:

1. **Filtro de alucinações**: lista configurável de frases (`app/captions/hallucinations_pt.txt`). Remover o segmento quando ele bate com a lista **e** está em trecho de baixa energia ou é o último segmento do vídeo.
2. **Repetições**: remover a mesma palavra/frase repetida 3 ou mais vezes seguidas.
3. **Duração mínima** de bloco: 0,3 s (estender o `end` sem invadir o próximo bloco).
4. **Sem sobreposição**: `end[i] <= start[i+1]`. Se sobrepor, ajustar `end[i] = start[i+1] - 0.001`.
5. **Fechar buracos pequenos**: se o intervalo entre blocos for menor que 0,15 s, emendar (evita que a legenda pisque).
6. **Baixa confiança**: marcar no transcript (`low_confidence: true`) em vez de apagar. A Sprint 2 (Gemini) e a Sprint 7 (editor) usam essa marcação.
7. Manter a correção dos milissegundos em `format_timestamp` (usar `round`, não truncar, e tratar 999,5 ms).

## ✅ Critérios de aceite

- [ ] Vídeo com 10 s de silêncio no fim não gera "Obrigado por assistir".
- [ ] Nenhum bloco com menos de 0,3 s ou sobreposto (teste automatizado que valida o SRT inteiro).
- [ ] Testes unitários para cada regra.

## 🔗 Dependências

Agrupar palavras em blocos.

<!-- issue: [S1] (Spike) Avaliar WhisperX / alinhamento forçado para tempos mais precisos | labels: enhancement, legendas, sprint-1 -->
## 🧩 Contexto

Os tempos por palavra do Whisper às vezes ficam **adiantados ou atrasados** em 100–300 ms. Para karaokê (Sprint 3) e cortes de silêncio (Sprint 4), isso aparece. O **WhisperX** faz um "alinhamento forçado" com um modelo wav2vec2 específico do idioma, o que deixa os tempos mais exatos.

> *Spike* = investigação com prazo curto (1–2 dias) para decidir se vale a pena. O resultado é uma **decisão documentada**, não necessariamente código em produção.

## 🛠️ O que fazer

1. Instalar o WhisperX num ambiente separado e rodar nos vídeos de benchmark.
2. Medir: precisão dos tempos (comparar visualmente alguns trechos no CapCut), WER, tempo de processamento, uso de memória, facilidade de instalar no Windows.
3. Testar também a alternativa mais simples: ajustar `vad_parameters` e `prepend_punctuations`/`append_punctuations` no faster-whisper.
4. Escrever a decisão num comentário desta issue: **adotar** (criar uma tarefa para integrar como etapa opcional `align`) ou **não adotar** (e por quê).

## ✅ Critérios de aceite

- [ ] Tabela comparativa e decisão registradas nesta issue.

## 🔗 Dependências

Benchmark de precisão.
