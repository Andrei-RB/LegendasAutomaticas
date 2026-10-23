<!-- epic: 🤖 S3 — Roteador de IA, juízes e consenso | labels: epic, sprint-3, ia -->
**Objetivo:** fazer a IA trabalhar de forma confiável, barata e com reservas.

**Pronto quando:** a ablação fica registrada e uma cota esgotada não quebra nada.

<!-- issue: [S3] Roteador de IA (provedores, cache, retry, registro) | labels: ia, backend, sprint-3 -->
**Objetivo:** ter um ponto único para todas as chamadas de IA.

- [ ] Provedores: `ollama`, `gemini`, `claude_cli` e `claude_api`.
- [ ] Tabela tarefa → cadeia de provedores.
- [ ] Cache por `sha256(tarefa + versao_prompt + modelo + payload)`.
- [ ] Validação Pydantic; em caso de erro, 1 retry e depois o próximo provedor.
- [ ] Prompts versionados em `ia/prompts/<tarefa>/vN.md`.
- [ ] Registro em `chamadas_ia`.
- [ ] Provedor `agy`: subprocesso sem shell, ambiente mínimo e área de trabalho efêmera em `/tmp/ia/<uuid>` com modo 0700.
- [ ] Família derivada do modelo, separada do provedor (`gemma` → google).
- [ ] Erros classificados: `AUTENTICACAO`, `COTA`, `REDE`, `INDISPONIVEL`, `TEMPO`, `RESPOSTA_VAZIA`, `ACAO_NEGADA`, `SAIDA_INVALIDA` e `VALIDACAO`. Repetem 1 vez apenas `RESPOSTA_VAZIA`, `ACAO_NEGADA`, `SAIDA_INVALIDA` e `VALIDACAO`.
- [ ] Migração `0003_ia`: campos novos em `chamadas_ia`, `julgamentos`, `candidatos` e `feedback`; tabela `cache_ia`.

**Aceite:** testes com provedores mockados cobrem cache, retry e troca de provedor.

<!-- issue: [S3] Orçamentos: Gemini gratuito e teto diário do Claude | labels: ia, sprint-3 -->
**Objetivo:** nunca estourar as cotas gratuitas.

- [ ] Contador diário no Redis por modelo do Gemini (RPD configurável, reserva de 20%). Erro 429 vai para a reserva.
- [ ] `CLAUDE_CHAMADAS_DIA` (padrão 10) e `CLAUDE_CHAMADAS_5H=4` por janela de 5 h, com no máximo 1 editor e 1 postagem por análise.
- [ ] Orçamento do agy por `/usage`, com reserva de 20% (uso até 80% da cota). Contador local como reserva da medição.
- [ ] Modo cego do agy: `AGY_MAX_CHAMADAS_5H=10` e `AGY_MAX_CHAMADAS_ANALISE=8`.
- [ ] Aviso na interface quando usar a reserva.

**Aceite:** com o limite zerado, o pipeline completa usando a reserva.

<!-- issue: [S3] Claude via assinatura (claude -p) com segurança | labels: ia, infra, sprint-3 -->
**Objetivo:** usar a assinatura do Claude dentro do Docker.

- [ ] `CLAUDE_MODE=subscription|api|off`; token gerado com `claude setup-token` em `CLAUDE_CODE_OAUTH_TOKEN`.
- [ ] O entrypoint aborta se `ANTHROPIC_API_KEY` existir no modo `subscription`.
- [ ] Rodar com `--allowedTools WebSearch`, num diretório vazio, com a transcrição delimitada como dado.
- [ ] Teste de contrato do adaptador.

**Aceite:** os três modos funcionam; uma fala do vídeo do tipo "ignore as instruções" não altera o resultado.

<!-- issue: [S3] Spike: Antigravity CLI (agy) no worker-ai | labels: ia, infra, sprint-3 -->
**Objetivo:** validar o `agy` no worker-ai antes de construir o provedor. Resultado em `docs/spike-agy.md`.

- [ ] Alvo `ai` em `infra/docker/Dockerfile.backend`: binário `agy` 1.4.6 em `/opt/agy/bin/agy`, dono root, com versão e sha256 fixados.
- [ ] Volume `agy_config` em `/tmp/agy-home/.gemini` (0700) e worker-ai com `target: ai`.
- [ ] `scripts/agy_login.sh` e `.ps1`, com login pelo fluxo URL + código.
- [ ] Testes T1–T16 em `scripts/spike_agy/`: clipes e lotes, prova por ID, delta do `/usage`, isolamento (`/dados`, `/proc/*/environ`, credencial, `../`, symlink), resposta vazia com ação negada, outros modelos, timeout e órfãos, concorrência, sem rede, sem login, injeção pelo vídeo e pela fala, login após 24 h e 72 h, binário imutável, pico de memória e prompt por stdin.
- [ ] Critérios G1–G9. Eliminatórios: G1, G2, G6 e G8. Ajustáveis: G3, G4, G5, G7 e G9.
- [ ] Planos B: keyring com fallback para arquivo; G6 falho → serviço `worker-agy` isolado; G9 falho → semáforo de 1 e `mem_limit 1536m`; inviável → chave Gemini com Gemma. O agy nunca roda no host.
- [ ] Fixtures anonimizadas em `backend/testes/ia/fixtures/agy/`. Nenhum código de produção entra no spike.

**Aceite:** relatório com G1, G2, G6 e G8 aprovados.

<!-- issue: [S3] Provedor agy por assinatura com controle de cota | labels: ia, backend, sprint-3 -->
**Objetivo:** chamar o agy com argumentos fixos, sem ampliar permissões, e medir a cota antes de cada chamada.

- [ ] `subprocesso.py` sem shell, com `start_new_session` e `killpg` no timeout; ambiente mínimo.
- [ ] argv fixo: `agy -p <prompt> --model <m> --output-format json --json-schema <schema> --print-timeout <t>`, com `<m>` em lista permitida.
- [ ] Prompt que não começa com `/`; transcrição delimitada como dado não confiável; dados grandes em `dados.json` na área de trabalho.
- [ ] Permissão só `read_file`. `denied_actions` não vazio vira `ACAO_NEGADA`.
- [ ] Semáforo Redis de 1 chamada por vez.
- [ ] Classificação do envelope, em ordem: timeout → `TEMPO`; exit ≠ 0 → padrões do stderr; saída sem JSON → `SAIDA_INVALIDA`; `status` ≠ `SUCCESS` → falha mapeada; `denied_actions` → `ACAO_NEGADA`; resposta vazia → `RESPOSTA_VAZIA`; tokens de entrada abaixo do piso para o vídeo → `VALIDACAO`.
- [ ] Parser de `/usage` com cache Redis, alimentando o orçamento.
- [ ] Teste de contrato `@pytest.mark.externo` em `backend/testes/ia/test_contrato_agy.py`.

**Aceite:** testes com binário falso cobrem envelope vazio, ação negada, timeout e cota.

<!-- issue: [S3] Juiz multimodal (Gemini assiste aos trechos; Gemma de reserva) | labels: ia, cortes, sprint-3 -->
**Objetivo:** avaliar os trechos olhando o vídeo.

- [ ] Top `min(2N, 16)` candidatos, em lotes de 4 clipes de 360p gerados de forma efêmera.
- [ ] Cadeia: agy `gemini-4-argon-medium` → Gemini API → Gemma 4 E4B (frames a cada 2 s + resumo dos sinais de áudio).
- [ ] Prova de visualização: a resposta devolve o ID de cada clipe visto, validado pelo código.
- [ ] A resposta traz a nota por critério e uma explicação de até 280 caracteres com citação literal (`frase_id`, trecho). A posição da citação é calculada pelo código.

**Aceite:** uma citação que não está na transcrição invalida o julgamento.

<!-- issue: [S3] Editor-chefe (Claude) + consenso + validadores | labels: ia, cortes, sprint-3 -->
**Objetivo:** ter a decisão final mais confiável possível.

- [ ] Editor às cegas: recebe os finalistas (`N+4`) sem as notas dos outros juízes; devolve ordem, variante (ID), motivo e título-gancho. Uma chamada por análise.
- [ ] Cadeia: Claude CLI → agy `claude-sonnet-5-5` → Qwen.
- [ ] Consenso: 1 voto por família; aprovado com ≥ 2 famílias acima do limiar (padrão 7,0). Gemini e Gemma contam como uma família só.
- [ ] Validadores: duração, frase completa, silêncio inicial ≤ 1,5 s, rosto visível em ≥ 60% do tempo.
- [ ] Corte sem juiz multimodal recebe a marca `sem_avaliacao_visual`.
- [ ] Com `AGY_MODE=off` e `CLAUDE_MODE=off`, Gemma + Qwen completam o pipeline.

**Aceite:** relatório de ablação (heurística → + Qwen → + Gemini → + Claude) no conjunto de ouro.

<!-- issue: [S3] Rubricas por perfil, aptidão por plataforma e ganchos | labels: ia, cortes, sprint-3 -->
**Objetivo:** ordenar os cortes por critérios de viralização e gerar ganchos ancorados no texto.

- [ ] Rubrica por formato: núcleo comum (gancho em 3 s, autonomia, desfecho, emoção, valor, ritmo e visual) de 0 a 10, com critérios por perfil: podcast (tensão, frase citável), gameplay (pico, reação, contexto), aula (insight, contraintuitivo, lista) e vlog (narrativa, payoff, humor).
- [ ] Aptidão por plataforma calculada pelo código, em função pura que só afeta a ordenação: TikTok com gancho ≤ 1,5 s; Shorts com `loop_possivel` citado; Reels com visual e rosto.
- [ ] Variações de gancho: 2 a 3 por corte (pergunta, afirmação, número, curiosidade, citação), até 60 caracteres, com `frase_id`. Números e palavras devem existir no corte.
- [ ] Explicação com citação: até 280 caracteres e 1 a 2 citações `{frase_id, trecho}`; a posição é calculada pelo código.
- [ ] Nenhum tempo de corte ou de gancho vem da IA.

**Aceite:** saída sem critério ou com citação inexistente é rejeitada.

<!-- issue: [S3] Galeria completa + painel de cotas | labels: frontend, sprint-3, ui -->
**Objetivo:** mostrar por que cada corte foi escolhido.

- [ ] Card: prévia em loop ao passar o mouse, notas por critério, concordância dos juízes, motivo, título-gancho e 👍/👎 com motivo (vai para `feedback`).
- [ ] Card: explicação com citações destacadas, ganchos e família de cada voto.
- [ ] Painel: cota restante do agy (Gemini de 5 h e semanal, Claude/GPT), da Gemini API e do Claude, uso local e histórico.

**Aceite:** o 👍/👎 fica salvo e as cotas atualizam.
