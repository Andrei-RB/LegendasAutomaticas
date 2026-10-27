# Schibsted Grotesk (subconjunto latino)

## 1. Origem

| Item | Valor |
|---|---|
| Família | Schibsted Grotesk variável (eixo de peso) |
| Fonte | Pacote `@fontsource-variable/schibsted-grotesk` 5.3.0 (repositório `schibsted/schibsted-grotesk`) |
| Licença | SIL Open Font License 1.1 (`OFL.txt`) |

## 2. Derivação

| Etapa | Ferramenta | Parâmetro |
|---|---|---|
| Limitar o eixo de peso | `fontTools.varLib.instancer` | `wght=400:700` |
| Subconjunto | `fontTools.subset` | `U+0020-007E`, `U+00A0-00FF`, `U+2013`, `U+2014`, `U+2018`, `U+2019`, `U+201C`, `U+201D`, `U+2022`, `U+2026`, `U+20AC` |
| Recursos de layout | `fontTools.subset` | `kern`, `tnum` |
| Formato | `--flavor=woff2 --no-hinting --desubroutinize` | `SchibstedGrotesk-latino.woff2`, 33 356 bytes |

## 3. Uso

`@font-face` com `font-weight: 400 700` e `font-display: swap`. A pilha do sistema permanece como reserva. A fonte não inclui a seta (`U+2192`); setas na interface são ícones desenhados.
