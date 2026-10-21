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

**Aceite:** testes com provedores mockados cobrem cache, retry e troca de provedor.

<!-- issue: [S3] Orçamentos: Gemini gratuito e teto diário do Claude | labels: ia, sprint-3 -->
**Objetivo:** nunca estourar as cotas gratuitas.

- [ ] Contador diário no Redis por modelo do Gemini (RPD configurável, reserva de 20%). Erro 429 vai para a reserva.
- [ ] `CLAUDE_CHAMADAS_DIA` (padrão 15), com no máximo 1 editor e 1 postagem por análise.
- [ ] Aviso na interface quando usar a reserva.

**Aceite:** com o limite zerado, o pipeline completa usando a reserva.

<!-- issue: [S3] Claude via assinatura (claude -p) com segurança | labels: ia, infra, sprint-3 -->
**Objetivo:** usar a assinatura do Claude dentro do Docker.

- [ ] `CLAUDE_MODE=subscription|api|off`; token gerado com `claude setup-token` em `CLAUDE_CODE_OAUTH_TOKEN`.
- [ ] O entrypoint aborta se `ANTHROPIC_API_KEY` existir no modo `subscription`.
- [ ] Rodar com `--allowedTools WebSearch`, num diretório vazio, com a transcrição delimitada como dado.
- [ ] Teste de contrato do adaptador.

**Aceite:** os três modos funcionam; uma fala do vídeo do tipo "ignore as instruções" não altera o resultado.

<!-- issue: [S3] Juiz multimodal (Gemini assiste aos trechos; Gemma de reserva) | labels: ia, cortes, sprint-3 -->
**Objetivo:** avaliar os trechos olhando o vídeo.

- [ ] Clipes do top 10 em 360p, de 3 a 5 por requisição, cada um com a etiqueta `ID:cX` gravada na imagem.
- [ ] Reserva Gemma 4 E4B: frames a cada 2 s + resumo dos sinais de áudio.
- [ ] A resposta traz o ID, a nota por critério e a citação.

**Aceite:** uma citação que não está na transcrição invalida o julgamento.

<!-- issue: [S3] Editor-chefe (Claude) + consenso + validadores | labels: ia, cortes, sprint-3 -->
**Objetivo:** ter a decisão final mais confiável possível.

- [ ] 1 chamada ao Claude por análise, com JSON compacto do top 10: devolve ordem, variante (ID), motivo e título-gancho.
- [ ] Consenso: 2 juízes de famílias diferentes com nota ≥ limiar.
- [ ] Validadores: duração, frase completa, silêncio inicial ≤ 1,5 s, rosto visível em ≥ 60% do tempo.

**Aceite:** relatório de ablação (heurística → + Qwen → + Gemini → + Claude) no conjunto de ouro.

<!-- issue: [S3] Galeria completa + painel de cotas | labels: frontend, sprint-3 -->
**Objetivo:** mostrar por que cada corte foi escolhido.

- [ ] Card: prévia em loop ao passar o mouse, notas por critério, concordância dos juízes, motivo, título-gancho e 👍/👎 com motivo (vai para `feedback`).
- [ ] Painel: quanto resta hoje do Gemini e do Claude, uso local e histórico.

**Aceite:** o 👍/👎 fica salvo e as cotas atualizam.
