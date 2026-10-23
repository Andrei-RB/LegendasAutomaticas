## O que muda

<!-- 1–3 linhas. -->

Closes #

## Como testei

- [ ] `ruff` + `pytest` verdes
- [ ] `vitest` verde (se mexeu no frontend)
- [ ] Testei o aceite da issue (descreva ou anexe print/vídeo)

## Interface (somente se mexeu em `frontend/` ou `pacotes/modelos-legenda/`)

- [ ] Protocolo `docs/protocolo-frontend.md` cumprido
- [ ] Capturas de antes e depois (1440 px e 390 px, escuro e claro)
- [ ] Métricas (INP, LCP, CLS, acessibilidade) e resultado de `vitest`, `playwright` e `tsc`
- [ ] Sem achado P0/P1 (impeccable) nem CRÍTICO/ALTO (revisores)
- [ ] Bibliotecas novas justificadas

## Checklist

- [ ] Funciona com IAs externas desligadas (reservas)
- [ ] Sem segredos; dados filtrados por `user_id`
- [ ] Docs atualizadas só se o comportamento visível mudou
