<!-- epic: 🛡️ S7 — Endurecimento, aprendizado e primeiro uso | labels: epic, sprint-7 -->
**Objetivo:** deixar o sistema robusto, fácil de instalar e pronto para virar serviço.

**Pronto quando:** o checklist de segurança está ok, o relatório de avaliação foi gerado e uma instalação limpa passa pelo assistente.

<!-- issue: [S7] Aprendizado com aprovações e rejeições | labels: cortes, backend, sprint-7 -->
**Objetivo:** o sistema melhorar com o uso.

- [ ] Tarefa semanal (beat): recalibrar os pesos por perfil com o `feedback` (regressão logística).
- [ ] Escolher exemplos para os prompts.
- [ ] Os vídeos aprovados entram no conjunto de ouro.
- [ ] O `feedback` grava `motivo_codigo` (enum) além do texto livre.

**Aceite:** precision@N no conjunto de ouro igual ou melhor depois da recalibração.

<!-- issue: [S7] Calibração com referências virais e concordância entre juízes | labels: ia, cortes, sprint-7 -->
**Objetivo:** medir se a nota acompanha o desempenho real e calibrar os limiares por família.

- [ ] Tabela `referencias_virais`: link, métricas digitadas (views, seguidores e data) e anotação.
- [ ] O vídeo de referência é processado localmente e apagado após 7 dias; ficam só as métricas e a anotação.
- [ ] Métricas: Spearman entre nota e log(views/seguidores); kappa entre famílias; AUC da nota contra 👍/👎 por versão de prompt.
- [ ] Limiares por família em `ia/limiares.yaml`, recalculados com os dados.

**Aceite:** Spearman(nota, log(views/seguidores)) ≥ 0,3 registrado no relatório.

<!-- issue: [S7] Retenção e uso de disco | labels: infra, backend, sprint-7 -->
**Objetivo:** não encher o disco.

- [ ] Beat apaga o original após 7 dias e os cortes após 30 (configurável).
- [ ] Aviso de disco cheio na interface.

**Aceite:** um teste com datas "envelhecidas" apaga os arquivos certos.

<!-- issue: [S7] Assistente de primeiro uso | labels: frontend, backend, sprint-7 -->
**Objetivo:** instalar sem sofrimento.

- [ ] Passos: testar a GPU → `ollama pull` com barra (SSE) → validar o token do Claude, a chave do Gemini e o `HF_TOKEN` → criar usuário.

**Aceite:** numa máquina limpa, o assistente chega ao fim sem editar arquivos.

<!-- issue: [S7] Saúde do sistema e configurações pela tela | labels: frontend, backend, sprint-7 -->
**Objetivo:** ver e configurar tudo pela interface.

- [ ] `/saude`: GPU, Ollama, tokens e disco, cada item com "como resolver".
- [ ] `/config`: chaves (criptografadas com Fernet), tetos, perfil padrão, @, CTA, hashtags fixas e lista de censura.

**Aceite:** nenhum segredo aparece em resposta da API nem em log.

<!-- issue: [S7] Segurança e limites | labels: backend, infra, sprint-7 -->
**Objetivo:** proteger o sistema para uso por outras pessoas.

- [ ] Rate limit por usuário e cotas por usuário.
- [ ] Revisão de path traversal, tamanho e MIME real.
- [ ] CORS/CSP para domínio próprio.

**Aceite:** o checklist de segurança está documentado nesta issue.

<!-- issue: [S7] Editor: atalhos, desfazer/refazer e celular | labels: frontend, sprint-7 -->
**Objetivo:** produtividade no PC e acesso pelo celular.

- [ ] Atalhos: Espaço, I/O, J/K/L, ←/→, Ctrl+Z e Ctrl+Shift+Z.
- [ ] Pilha de comandos para desfazer/refazer.
- [ ] Layout de celular para biblioteca, galeria e postagens.

**Aceite:** o fluxo de revisão funciona só com o teclado; Lighthouse no celular ≥ 85.

<!-- issue: [S7] Observabilidade + docs curtas | labels: docs, infra, sprint-7 -->
**Objetivo:** saber o que acontece e como usar o sistema.

- [ ] Tempo por etapa, chamadas e custo por análise no painel.
- [ ] README curto: instalar, usar e resolver problemas.

**Aceite:** uma pessoa nova instala e usa só com o README.
