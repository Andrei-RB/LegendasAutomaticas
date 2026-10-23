# Plano de IA por assinatura (agy) e melhoria de viralização

Complementa o [`plano-v2.md`](plano-v2.md) (decisões D41–D54). Em caso de conflito, prevalece este documento.

## 1. Contexto

Teste no host Windows (2026-10-23): o Antigravity CLI (`agy` 1.4.6), sucessor do Gemini CLI para contas AI Pro, roda em modo headless por subprocesso. O modelo `gemini-4-argon-medium` analisou um clipe mp4 em 360p e identificou cor, texto na tela, momento da mudança e fala, com saída JSON validada por schema. A cota da assinatura é consultada por `agy -p /usage`. A chave do AI Studio passa a ser reserva.

O pacote `backend/app/ia/` ainda não tem implementação. O roteador e os provedores estão previstos para a S3 (`docs/sprints/sprint-3.md`).

Escopo definido:
- uso só pessoal;
- conteúdo: podcast, gameplay, aula e vlog;
- TikTok, Shorts e Reels com o mesmo peso;
- 5–10 cortes de 30–60 s por vídeo, só em pt-BR;
- o agy roda dentro do worker-ai, com spike antes;
- agy como principal no juiz, chave como reserva;
- Claude via agy como reserva do editor;
- Claude Pro;
- até 80% das cotas das assinaturas;
- revisão manual sempre;
- aprendizado por 👍/👎, métricas manuais e referências externas (APIs ficam para depois);
- extras: ganchos, temas em alta, explicação da nota, quase-aprovados;
- spike antes da S3; o restante na S3, S6 e S7.

## 2. Restrições encontradas no repositório

| Achado | Consequência |
|---|---|
| rootfs `read_only`, `/tmp` tmpfs `noexec`, `HOME=/tmp` | O binário agy fica fixo na imagem (`/opt/agy/bin/agy`, root, versão e sha256 fixados). O auto-update não consegue executar |
| A worker-ai tem `DATABASE_URL`, `REDIS_URL` e chaves no ambiente, com o mesmo uid do agy | Subprocesso com ambiente mínimo. Teste eliminatório de isolamento (G6); se falhar, serviço `worker-agy` separado |
| O executor só aceita saídas declaradas | Os clipes 360p são gerados de forma efêmera numa área temporária por chamada |
| Gemma é da família Google | Gemini + Gemma não vale como consenso. Famílias: google, anthropic, alibaba (Qwen), openai (gpt-oss) |
| `ChamadaIa` e `Julgamento` não têm família, versão de prompt nem tipo de erro | Migração `0003_ia` |
| Claude Pro tem limite baixo; `CLAUDE_CHAMADAS_DIA` está em 50 | Novo padrão: 10 por dia e 4 por janela de 5 h |
| Argumento de argv limitado a 128 KiB | Dados grandes vão em `dados.json` na área de trabalho, ou por stdin se o T16 passar |

## 3. Fase 1: Spike `s3/spike-agy` (logo após a S0)

Entregas:
- alvo `ai` em `infra/docker/Dockerfile.backend` (estágios `base` → `agy` com sha256 → `ai`);
- worker-ai com `target: ai` e volume `agy_config:/tmp/agy-home/.gemini` (0700);
- `scripts/agy_login.sh` e `.ps1`, com login pelo fluxo URL + código;
- `scripts/spike_agy/`;
- `docs/spike-agy.md`;
- fixtures anonimizadas em `backend/testes/ia/fixtures/agy/`.

Nenhum código de produção entra no spike.

**Testes T1–T16** (uid 10001, `read_only`):

| ID | Teste |
|---|---|
| T1 | 1 clipe |
| T2 | Lote de 4 clipes de 45 s, 10 vezes |
| T3 | Prova de visualização por ID |
| T4 | Delta do `/usage` por chamada |
| T5 | Isolamento: `/dados`, `/proc/*/environ`, credencial, `../`, symlink |
| T6 | Resposta vazia com ação negada |
| T7 | Claude e gpt-oss via agy |
| T8 | Timeout e processos órfãos |
| T9 | 2 chamadas simultâneas |
| T10 | Sem rede |
| T11 | Sem login |
| T12 | Injeção de prompt pelo vídeo e pela fala |
| T13 | Login persiste após recriar o contêiner, 24 h e 72 h |
| T14 | Binário imutável; resíduos no HOME |
| T15 | Pico de memória |
| T16 | Prompt por stdin |

**Go/no-go:**

| Critério | Limite | Tipo |
|---|---|---|
| G1 | Login persiste 72 h | eliminatório |
| G2 | Sem root e sem `--dangerously-skip-permissions` | eliminatório |
| G3 | ≥ 9 de 10 lotes válidos; p95 ≤ 120 s | ajustável |
| G4 | ≥ 95% de atribuição visual correta | ajustável |
| G5 | ≤ 10% da cota Gemini de 5 h por análise | ajustável |
| G6 | 100% das leituras fora da área negadas | eliminatório |
| G7 | Falhas distinguíveis | ajustável |
| G8 | Binário imutável | eliminatório |
| G9 | Pico ≤ 850 MB | ajustável |

**Planos B:**

| Falha | Plano |
|---|---|
| Keyring | Fallback para arquivo; depois `gnome-keyring` com dbus |
| G6 | B2: serviço `worker-agy` sem `dados` e sem segredos, fila `ai_agy`, volume `clipes_ia` |
| G9 | Semáforo de 1 + `mem_limit 1536m` |
| Inviável | B3: plano-v2 original (chave Gemini → Gemma). Nunca rodar o agy no host |

## 4. Fase 2: Docs `docs/ia-agy`

Registra as decisões antes do spike. Os valores medidos no spike (latência, consumo de cota, memória) atualizam este documento e os padrões de configuração ao fim da Fase 1.

1. **`docs/plano-v2.md`**: decisões D41–D54.

| Decisão | Conteúdo |
|---|---|
| D41 | agy por assinatura, `AGY_MODE=off` por padrão, risco de termos de uso aceito para uso pessoal |
| D42 | Família separada do provedor |
| D43 | Cadeia do juiz |
| D44 | Cadeias do editor e das postagens |
| D45 | Até 80% das cotas via `/usage` + contador local |
| D46 | Funil + editor às cegas (não vê as notas dos outros juízes; muda o plano atual) |
| D47 | Perfis podcast, gameplay, aula e vlog |
| D48 | Ganchos |
| D49 | Temas em alta |
| D50 | Explicação com citação + prova de visualização |
| D51 | Quase-aprovados |
| D52 | Referências externas |
| D53 | Métricas manuais e coletores |
| D54 | Revisão manual obrigatória |

   Atualizar também as seções Roteador, Orçamentos, Anti-alucinação, Avaliação e Riscos.
2. **`CLAUDE.md`**: §5.5, §6 (tabela de roteamento), §12 (linha agy) e §13 (proibido `--dangerously-skip-permissions`).
3. **`sprint-3.md`**, issues novas:
   - Spike agy;
   - Provedor agy com cota por `/usage`;
   - Rubricas por perfil, explicação e ganchos.

   Nas issues existentes, só o corpo muda e os títulos ficam intactos, porque a sincronização encontra as issues pelo título.
4. **`sprint-6.md`**, issues novas: temas em alta, sugestões de quase-aprovados, publicações e métricas manuais.
5. **`sprint-7.md`**, issue nova: calibração com referências externas e concordância entre juízes.
6. **`sprint-9-backlog.md`**: coletores por API, proxy de saída com lista de domínios permitidos, `worker-agy` dedicado.

## 5. Fase 3: S3, camada de IA (`backend/app/ia/`)

### Módulos

| Módulo | Função |
|---|---|
| `tipos.py` | `Familia`, `Tarefa`, `Anexo`, `PedidoIa`, `ResultadoIa` |
| `familias.py` | A família sai do modelo (`gemma` → google) |
| `erros.py` | `ErroProvedor`: `AUTENTICACAO`, `COTA`, `REDE`, `INDISPONIVEL`, `TEMPO`, `RESPOSTA_VAZIA`, `ACAO_NEGADA`, `SAIDA_INVALIDA`, `VALIDACAO`. Só os 4 últimos repetem 1 vez |
| `subprocesso.py` | `executar_cli(argv, cwd, env, timeout_s)`: sem shell, `start_new_session`, `killpg` no timeout, saída truncada. Reutilizado pelo `claude_cli` |
| `ambiente.py` | `ambiente_minimo()` |
| `area_trabalho.py` | `/tmp/ia/<uuid>` com 0700, anexos `<id>.mp4`, removida em `finally` |
| `provedores/base.py` | Protocolo `Provedor` |
| `provedores/agy.py` | Provedor agy |
| `provedores/envelope_agy.py` | Classificação pura do envelope |
| `provedores/uso_agy.py` | Parser do `/usage`, cache Redis |
| `provedores/ollama.py`, `gemini_api.py`, `claude_cli.py` | Demais provedores |
| `orcamento.py` | Reserva de 20%, modo cego, limite por análise |
| `cache.py` | Tabela `cache_ia` no Postgres. Chave: user + tarefa + versão do prompt + modelo + dados + sha256 dos anexos |
| `validacao.py` | Schema, IDs, lote completo, citação literal, prova visual, varredura de segredos |
| `cadeias.py` | Cadeias por tarefa |
| `roteador.py` | Fluxo do roteador |
| `registro_chamadas.py` | Só hash, tamanhos, tokens e tipo de erro |
| `consenso.py` | Consenso por família |
| `prompts/<tarefa>/v1.md`, `rubricas/<perfil>.yaml` | Prompts e rubricas versionados |

Reutilizar do pipeline:
- `Etapa`, `Passo`, `ContextoPasso` e `RegistroEtapas` (`backend/app/pipeline/executor.py`);
- `ErroPipeline` e `MENSAGENS` (`pipeline/erros.py`), com o novo código `IA_INDISPONIVEL`;
- `PublicadorEventos` (`pipeline/eventos.py`), com o novo tipo `aviso` para uso de reserva;
- `enfileirar_etapa` (`pipeline/tarefas.py`).

### Provedor agy

**argv:**

```
[agy, -p, prompt, --model, m, --output-format, json, --json-schema, schema, --print-timeout, t]
```

- O modelo precisa estar na lista permitida.
- O prompt não pode começar com `/`.
- A transcrição vai delimitada como dado não confiável.
- Semáforo Redis de 1 chamada.

**Classificação, em ordem:**

| Ordem | Condição | Resultado |
|---|---|---|
| 1 | Timeout | `TEMPO` |
| 2 | exit ≠ 0 | padrões do stderr |
| 3 | Saída não é JSON | `SAIDA_INVALIDA` |
| 4 | `status` ≠ `SUCCESS` | falha mapeada |
| 5 | `denied_actions` não vazio | `ACAO_NEGADA` |
| 6 | Resposta vazia | `RESPOSTA_VAZIA` (caso observado com o Flash) |
| 7 | Tokens de entrada abaixo do piso para o vídeo | `VALIDACAO` |

### Cadeias

| Tarefa | Cadeia |
|---|---|
| Triagem | Qwen → regras |
| Juiz | agy `gemini-4-argon-medium` → Gemini API (chave) → Gemma |
| Editor-chefe e postagens | Claude CLI → agy `claude-sonnet-5-5` → Qwen |
| Temas e hashtags | Claude CLI + WebSearch (cache de 24 h) |

### Funil por vídeo de 1 h

| Estágio | Regra | Chamadas |
|---|---|---|
| Candidatos | 30–40 | — |
| Triagem Qwen | todos | locais |
| Juiz | top `min(2N, 16)` em lotes de 4 | 4–5 agy |
| Editor | finalistas `N+4`, às cegas | 1 Claude |
| Postagens | 1–2 | Claude |

Por análise: cerca de 5 chamadas agy e 3 Claude. Isso dá cerca de 3 análises por dia antes de o Claude Pro passar para o Claude via agy.

### Consenso

- 1 voto por família.
- Aprovado com validadores determinísticos OK e ≥ 2 famílias acima do limiar (`ia/limiares.yaml`, padrão 7,0).
- Sem nenhum juiz multimodal, o corte recebe a marca `sem_avaliacao_visual`.
- Com tudo externo desligado, Gemma + Qwen mantêm o pipeline funcionando.

### Migração `0003_ia`

| Tabela | Mudança |
|---|---|
| `chamadas_ia` | `familia`, `versao_prompt`, `tentativa`, `erro_tipo`, `chave_cache`, `grupo_cota`, `cota_restante_pct` |
| `julgamentos` | `provedor`, `familia`, `explicacao`, `prova_visual` |
| `candidatos` | `origem`, `candidato_pai_id` |
| `cache_ia` | nova |
| `feedback` | `motivo_codigo` |

### Configuração

- **`backend/app/nucleo/config_ia.py`**:
  - `AGY_MODE` (padrão `off`), `AGY_BIN`, `AGY_HOME`, `AGY_TIMEOUT_S=180`, `AGY_RESERVA_PCT=20`, `AGY_MAX_CHAMADAS_5H=10`, `AGY_MAX_CHAMADAS_ANALISE=8`, `AGY_CONCORRENCIA=1`;
  - modelos permitidos;
  - `IA_CLIPES_POR_LOTE=4`, `IA_LIMIAR_PADRAO=7`, `IA_QUASE_MARGEM=1.0`, `CLAUDE_CHAMADAS_5H=4`.
- **`infra/.env.example`**: as mesmas chaves e `CLAUDE_CHAMADAS_DIA=10`.
- **`infra/entrypoints/worker-ai.sh`**: valida `AGY_MODE` e fixa `permissions.allow` = só `read_file`; desliga auto-update e telemetria; avisa se não houver credencial.

## 6. Fase 4: Melhorias de viralização (S3, S6, S7)

| Melhoria | Mecanismo | Validação |
|---|---|---|
| Rubrica por formato (S3) | Núcleo comum: gancho 3 s, autonomia, desfecho, emoção, valor, ritmo e visual. Critérios extras por perfil: podcast (tensão, frase citável), gameplay (pico, reação, contexto), aula (insight, contraintuitivo, lista), vlog (narrativa, payoff, humor) | Todos os critérios presentes, de 0 a 10 |
| Aptidão por plataforma (S3) | Calculada pelo código: TikTok com gancho ≤ 1,5 s; Shorts com `loop_possivel` citado; Reels com visual e rosto | Função pura; afeta só a ordenação |
| Variações de gancho (S3/S6) | 2–3 por corte (pergunta, afirmação, número, curiosidade, citação), ≤ 60 caracteres, com `frase_id` | Números e palavras existem no corte |
| Explicação com citação (S3) | ≤ 280 caracteres + 1–2 citações {frase_id, trecho} | Citação literal; a posição é calculada pelo código |
| Quase-aprovados (S3/S6) | O código gera opções de ajuste por ID (variantes, ±1–3 frases, limites de cena); o editor escolhe `ajuste_id`; nasce um candidato `origem=ajuste` que aparece em "Sugestões" | Nunca há tempos de LLM; os validadores rodam de novo |
| Temas em alta (S6) | Claude + WebSearch, cache de 24 h por nicho; a triagem devolve `temas_ids` | O código confirma a palavra-chave no texto; peso 0,5; não entra no consenso |
| Referências externas (S7) | Tabela `referencias_virais` com métricas digitadas e anotação; vídeo processado localmente e apagado em 7 dias | Meta: Spearman(nota, log(views/seguidores)) ≥ 0,3 |
| Métricas manuais (S6/S7) | Tabelas `publicacoes` e `metricas_publicacao`; `Protocol ColetorMetricas` com `ColetorManual`. APIs ficam no backlog | Faixas válidas |

**Medição do ganho** (`backend/avaliacao/`):
- ablação no conjunto de ouro: heurística, +Qwen, +Gemini, +Claude, consenso de 2 famílias contra juiz único;
- precision@N e recall@N;
- concordância entre famílias (Spearman e kappa);
- AUC da nota contra 👍/👎 por versão de prompt;
- correlação nota × retenção a partir de 20 publicações;
- custo em cota por análise.

## 7. Segurança e riscos

| Risco | Mitigação |
|---|---|
| Injeção pela transcrição, pela tela ou pelo áudio | Só `read_file`; `denied_actions` vira falha; cwd só com os clipes; schema estrito; saída só com IDs e notas |
| Leitura de segredos ou `/dados` | Ambiente mínimo; G6; plano B2 |
| Credencial OAuth no volume | 0700/0600, montada só no serviço; revogação documentada |
| Auto-update e cadeia de suprimentos | Versão e sha256 fixados; rootfs `read_only`; HOME `noexec` |
| Termos de uso | Automação com OAuth da assinatura não é explicitamente permitida: risco de suspensão da conta. Uso só pessoal; `off` por padrão; chave como reserva; nunca SaaS |
| Mudança de formato do envelope ou do `/usage` | Teste de contrato `@pytest.mark.externo`; modo cego conservador |

## 8. Verificação

1. **Spike:** `docs/spike-agy.md` com T1–T16 medidos e G1, G2, G6 e G8 aprovados. `docker compose exec worker-ai pytest -m externo backend/testes/ia/test_contrato_agy.py`.
2. **S3:** `ruff` + `pytest backend -m "not lento"` com fakes alimentados pelas fixtures reais:
   - argv;
   - envelope (incluindo resposta vazia e ação negada);
   - retry e troca de provedor;
   - ambiente mínimo;
   - área de trabalho;
   - parser do `/usage` e reserva de 20%;
   - cache;
   - consenso (Gemini + Gemma não aprova; Gemma + Qwen aprova);
   - citação, gancho, ajuste por ID;
   - logs sem segredos.
3. **E2E:**
   - vídeo real de 1 h com `AGY_MODE=subscription`: 5–10 cortes, cada um com explicação, citações, 2–3 ganchos e votos de ≥ 2 famílias; `/usage` acima de 20% ao final;
   - `AGY_MODE=off` + `CLAUDE_MODE=off`: o pipeline completa com Gemma + Qwen.
4. **Ablação** registrada em `backend/avaliacao/` antes de fechar a S3.
5. **Fluxo do projeto** em cada PR: `/verificar` até `STATUS: OK`, `/revisar`, `/conformidade`, PR com `Closes #N`, `graphify update .`. Merge só com autorização.

## 9. Ordem

1. `docs/ia-agy` (decisões e issues).
2. `s3/spike-agy`, após a S0.
3. S1 e S2 normalmente.
4. S3:
   1. base;
   2. orçamento;
   3. provedores;
   4. juiz;
   5. editor e consenso;
   6. rubricas e ganchos;
   7. galeria e painel de cotas.
5. S6: temas, sugestões, métricas manuais.
6. S7: calibração e limiares por família.
