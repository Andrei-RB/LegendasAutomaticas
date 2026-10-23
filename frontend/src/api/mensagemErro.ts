import { ErroApi } from "./erros";

export type ChaveErro = "erros.rede" | "erros.ocupado" | "erros.generico";

export function chaveErro(erro: unknown): ChaveErro {
  if (!(erro instanceof ErroApi)) return "erros.generico";
  if (erro.status === 0) return "erros.rede";
  if (erro.status === 429 || erro.status === 503) return "erros.ocupado";
  return "erros.generico";
}
