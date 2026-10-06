<!-- epic: 🤖 Sprint 2 — Integração com Gemini (revisão, emojis e destaques) | labels: epic, sprint-2, ia -->
## 🎯 Objetivo da Sprint

Usar o **Gemini** (API do Google AI Studio) como "revisor e editor" da legenda:

- corrigir palavras que o Whisper ouviu errado, usando o contexto da frase;
- adicionar **emojis** 🔥 e destacar **palavras-chave**;
- tudo **sem estragar os tempos** que vieram do Whisper.

## 🧠 Divisão de papéis

| IA | Ponto forte | Função no projeto |
|---|---|---|
| **Whisper** (local) | Sabe **quando** cada palavra é dita | Transcrição + tempos |
| **Gemini** (nuvem) | Entende **o que** está sendo dito | Revisão, emojis, destaques, ideias |

## 💰 Sobre custo e chave (resumo)

- A chave é criada em https://aistudio.google.com ("Get API key").
- A assinatura Gemini Pro (app) **não** cobre a API, que é cobrada à parte.
- Existe um **nível gratuito** com limites de requisições por minuto/dia. No nível gratuito, o Google pode usar os dados para melhorar os produtos.
- Só há cobrança se você ativar o faturamento num projeto Google Cloud.
- Revisar um vídeo de 10 min com um modelo "Flash" custa frações de centavo.
- Verificar preços e limites atuais em https://ai.google.dev/pricing

## ✅ Definição de pronto (DoD)

- [ ] O app funciona **normalmente sem chave** (Gemini é opcional).
- [ ] Com a chave + opção ligada, a legenda é revisada, com emojis e destaques.
- [ ] Os tempos das palavras **nunca** são alterados pelo Gemini.
- [ ] Falhas do Gemini (limite, rede, resposta inválida) não derrubam o job: o sistema segue com a legenda original e avisa.
- [ ] Documentação de configuração no README.

## 📋 Tarefas

As tarefas estão listadas como sub-issues abaixo.

<!-- issue: [S2] Configurar cliente Gemini (google-genai) com retries, timeout e modo sem chave | labels: enhancement, ia, sprint-2 -->
## 🧩 Contexto

Precisamos de um único ponto do código que conversa com o Gemini, para que as outras features (revisão, emojis, cortes virais, títulos, tradução) reutilizem a mesma configuração, o mesmo tratamento de erro e o mesmo controle de custo.

## 🛠️ O que fazer

1. `pip install google-genai` e adicionar ao `requirements.txt`.
2. Configurações no `.env` / `config.py`:
   ```
   GEMINI_API_KEY=            # vazio = recursos de IA desligados
   GEMINI_MODEL=gemini-2.5-flash   # confira o nome mais recente no AI Studio
   GEMINI_TIMEOUT_S=60
   GEMINI_MAX_RETRIES=3
   ```
3. Criar `app/services/gemini_service.py` com:
   - `is_enabled() -> bool` (há chave?);
   - `generate_json(prompt, schema, *, temperature=0.2) -> dict | list`, que pede **resposta em JSON estruturado** (`response_mime_type="application/json"` + `response_schema`);
   - **retry com backoff exponencial** (2 s, 4 s, 8 s) para erros 429 (limite) e 5xx;
   - **sem retry** para 400/403 (chave inválida, conteúdo bloqueado);
   - log de uso: tokens de entrada/saída (`response.usage_metadata`) por job.
4. Endpoint/health: `GET /api/v1/health` passa a informar `"gemini": "enabled" | "disabled"` (sem revelar a chave).
5. Frontend: se o Gemini estiver desligado, as opções de IA aparecem desabilitadas, com a dica "Configure GEMINI_API_KEY no .env".
6. **Segurança**: a chave nunca vai para log, resposta da API ou frontend. Conferir que `.env` está no `.gitignore`.

## 💡 Exemplo de código

```python
import os, time, json
from google import genai
from google.genai import types, errors
from app.core.config import settings

_client = None

def is_enabled() -> bool:
    return bool(settings.GEMINI_API_KEY)

def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client

def generate_json(prompt: str, schema, temperature: float = 0.2):
    for tentativa in range(settings.GEMINI_MAX_RETRIES + 1):
        try:
            resp = _get_client().models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=temperature,
                    response_mime_type="application/json",
                    response_schema=schema,
                ),
            )
            return json.loads(resp.text)
        except errors.APIError as e:
            if e.code in (429, 500, 502, 503, 504) and tentativa < settings.GEMINI_MAX_RETRIES:
                time.sleep(2 ** (tentativa + 1))
                continue
            raise
```

## ✅ Critérios de aceite

- [ ] Sem `GEMINI_API_KEY`, nenhuma chamada é feita e o app funciona igual.
- [ ] Erro 429 é tentado de novo automaticamente.
- [ ] Testes com o cliente **mockado** (o CI não usa a chave real).
- [ ] Teste "slow"/manual que faz uma chamada real quando a variável existe.

## 🔗 Dependências

Pipeline da Sprint 0.

<!-- issue: [S2] Revisão da transcrição pelo Gemini preservando os tempos (índices) | labels: enhancement, ia, legendas, sprint-2 -->
## 🧩 Contexto

O Whisper erra palavras que soam parecidas ("ensina" × "ensinar", "mais" × "mas", "capicute" × "CapCut"). Uma IA de linguagem corrige isso pelo contexto. O problema é que, se pedirmos "corrija este texto", ela devolve um texto novo e **perdemos o tempo de cada palavra**.

**Solução:** mandar cada palavra **com um número (índice)** e exigir a mesma quantidade de itens, com os mesmos índices, na resposta.

## 🛠️ O que fazer

1. Nova etapa do pipeline: `app/pipeline/steps/gemini_review.py` (roda se `options.ai_review`).
2. Dividir o transcript em **lotes de ~250 palavras**, cortando sempre em fim de frase, e mandar ~30 palavras do lote anterior como **contexto somente leitura**.
3. Enviar para cada palavra: `i`, `w` (texto) e `lc` (baixa confiança, vindo da Sprint 1), para o modelo focar nas palavras duvidosas.
4. Incluir no prompt o **vocabulário** do usuário e o idioma.
5. **Validar a resposta** antes de aplicar:
   - a mesma quantidade de itens e os mesmos índices;
   - nenhuma "palavra" com mais de 3 palavras (o modelo não pode juntar frases num índice só);
   - se a validação falhar, **tentar 1 vez de novo**; se falhar de novo, manter o lote original e registrar um aviso no job.
6. Guardar o texto original em `original_text` em cada palavra alterada (permite comparar e desfazer no editor da Sprint 7).
7. Atualizar o progresso por lote ("Revisando com IA... lote 3 de 8").

## 💡 Prompt base

```
Você é revisor de legendas em {idioma} de vídeos para redes sociais.
Abaixo há uma lista de palavras transcritas automaticamente, cada uma com um índice "i".
Itens com "lc": true têm baixa confiança e provavelmente estão errados.

Regras:
1. Corrija erros de transcrição usando o contexto (ortografia, concordância, palavras que soam parecidas).
2. Corrija nomes próprios e termos usando este vocabulário: {vocabulario}.
3. Ajuste maiúsculas e pontuação no início/fim das frases.
4. NÃO junte, separe, remova ou adicione itens. Devolva EXATAMENTE os mesmos índices.
5. Se uma palavra estiver correta, devolva igual.

Contexto anterior (não devolver): {contexto}
Palavras: {json_lote}
```

Schema da resposta: `[{"i": int, "w": str}]`

## 💡 Exemplo

```
Antes:  hoje | vou | ensina | como | ganha | dinheiro | no | capicute
Depois: Hoje | vou | ensinar | como | ganhar | dinheiro | no | CapCut
Tempos: idênticos ✅
```

## ✅ Critérios de aceite

- [ ] O WER no benchmark cai em relação à Sprint 1 (registrar o número).
- [ ] Teste automatizado: com o Gemini mockado devolvendo itens a menos, o lote original é mantido.
- [ ] Os campos `start`/`end` nunca mudam (teste compara antes/depois).
- [ ] Falha total do Gemini → o job termina com sucesso, com aviso "Revisão por IA indisponível".

## 🔗 Dependências

Cliente Gemini; Sprint 1 (baixa confiança e vocabulário).

<!-- issue: [S2] Emojis e destaque de palavras-chave via Gemini | labels: enhancement, ia, legendas, sprint-2 -->
## 🧩 Contexto

Legendas de Reels/Shorts com mais engajamento usam **emojis** no fim de palavras importantes e **destaques** (MAIÚSCULAS ou cor diferente) em palavras-chave. Emoji funciona direto no `.srt` e no CapCut, porque é texto. A cor do destaque entra na Sprint 3 (`.ass`).

## 🛠️ O que fazer

1. Pode rodar na mesma chamada da revisão (economiza tokens) ou numa etapa separada `gemini_enrich`. Decidir pela qualidade no teste.
2. Opções do job:
   - `emojis: "none" | "few" | "many"` (poucos: no máximo 1 a cada ~2 frases; muitos: até 1 por frase);
   - `highlight_keywords: bool`;
   - `highlight_style: "uppercase" | "color" | "both"` (`color` só tem efeito no `.ass`).
3. Resposta do Gemini por palavra: `{"i": 12, "emoji": "💰", "highlight": true}`, apenas para as palavras que mudam.
4. Regras no prompt:
   - emoji **relevante ao sentido** (dinheiro 💰, fogo/impacto 🔥, ideia 💡, atenção ⚠️, risada 😂);
   - nada de emoji em palavras de ligação (de, que, o, a);
   - destaques: substantivos/verbos centrais, números, promessas ("GRÁTIS", "3 PASSOS");
   - no máximo ~15% das palavras destacadas.
5. Validação: o emoji tem que ser **1 emoji Unicode válido** (biblioteca `emoji`, `emoji.is_emoji`). Senão, descartar.
6. Gerador SRT: anexar o emoji depois da palavra (`dinheiro 💰`) e, com `uppercase`, escrever em maiúsculas.
7. Frontend: "Emojis: Nenhum / Poucos / Muitos" e "Destacar palavras-chave ☑".

## 💡 Exemplo de saída

```
1
00:00:00,520 --> 00:00:01,100
Hoje vou ensinar

2
00:00:01,100 --> 00:00:01,900
como GANHAR DINHEIRO 💰
```

## ✅ Critérios de aceite

- [ ] Com "Poucos", a densidade de emojis respeita o limite.
- [ ] Emojis inválidos ou texto no lugar de emoji são descartados (teste).
- [ ] SRT com emoji importado no CapCut aparece corretamente (teste manual com print anexado ao PR).

## 🔗 Dependências

Revisão da transcrição pelo Gemini.

<!-- issue: [S2] Documentar uso da chave Gemini (README + .env.example) | labels: docs, ia, sprint-2 -->
## 🧩 Contexto

Quem clonar o projeto (inclusive você no futuro) precisa saber como ativar a IA, quanto custa e quais são os riscos.

## 🛠️ O que fazer

Seção "🤖 Recursos de IA (Gemini)" no README com:

1. **Passo a passo com prints**: aistudio.google.com → Get API key → Create API key → copiar.
2. Onde colar: `.env` → `GEMINI_API_KEY=...`, e reiniciar o worker.
3. **Custos**: assinatura do app ≠ API; nível gratuito com limites; cobrança só com faturamento ativo; link para a página de preços oficial.
4. **Privacidade**: no nível gratuito o Google pode usar os dados para melhorar os produtos; o que é enviado (só o **texto** da transcrição, não o vídeo, a não ser nas features que usam imagem, como a thumbnail da Sprint 6).
5. **Segurança**: nunca commitar a chave; como revogar uma chave vazada no AI Studio.
6. **Erros comuns**: 429 (limite atingido: espere ou reduza o uso), 403 (chave inválida/sem permissão), 400 (modelo com nome errado).
7. Atualizar o `.env.example` com todas as novas variáveis comentadas.

## ✅ Critérios de aceite

- [ ] Uma pessoa sem experiência consegue ativar a IA só lendo o README.

## 🔗 Dependências

Cliente Gemini.

<!-- issue: [S2] Controle de uso e cache das chamadas de IA | labels: enhancement, ia, sprint-2 -->
## 🧩 Contexto

Reprocessar o mesmo vídeo (ou trocar só o tema da legenda) não deveria gastar a cota do Gemini de novo. Também é útil saber quanto cada job consumiu.

## 🛠️ O que fazer

1. **Cache por conteúdo**: chave = `sha256(modelo + prompt + entrada)`; valor = resposta JSON. Guardar no Redis com TTL de 7 dias (ou em `cache/gemini/` em disco).
2. Registrar por job, em `outputs/<job_id>/ai_usage.json`: número de chamadas, tokens de entrada/saída, quantas vieram do cache e o tempo total.
3. Limite de segurança por job: `GEMINI_MAX_CALLS_PER_JOB=50`. Passou disso, parar as chamadas de IA e seguir sem elas.
4. Mostrar no frontend, ao fim do job: "IA: 6 chamadas, 12.400 tokens".

## ✅ Critérios de aceite

- [ ] Processar duas vezes a mesma transcrição com as mesmas opções faz **zero** chamadas novas.
- [ ] O limite por job é respeitado (teste com mock).

## 🔗 Dependências

Cliente Gemini.
