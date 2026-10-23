import type { z } from "zod";
import { ErroApi, ErroRespostaInvalida } from "./erros";

const PREFIXO = "/api/v1";

type AoNaoAutenticado = () => void;
let aoNaoAutenticado: AoNaoAutenticado | null = null;

export function definirAoNaoAutenticado(funcao: AoNaoAutenticado | null): void {
  aoNaoAutenticado = funcao;
}

export interface OpcoesRequisicao<T> {
  esquema: z.ZodType<T>;
  metodo?: "GET" | "POST";
  corpo?: unknown;
  notificar401?: boolean;
}

async function lerJson(resposta: Response): Promise<unknown> {
  try {
    return await resposta.json();
  } catch {
    return undefined;
  }
}

export async function requisitar<T>(caminho: string, opcoes: OpcoesRequisicao<T>): Promise<T> {
  const { esquema, metodo = "GET", corpo, notificar401 = true } = opcoes;
  const cabecalhos: Record<string, string> = { Accept: "application/json" };
  const init: RequestInit = { method: metodo, credentials: "same-origin", headers: cabecalhos };
  if (corpo !== undefined) {
    cabecalhos["Content-Type"] = "application/json";
    init.body = JSON.stringify(corpo);
  }

  let resposta: Response;
  try {
    resposta = await fetch(`${PREFIXO}${caminho}`, init);
  } catch {
    throw new ErroApi(0);
  }

  if (!resposta.ok) {
    const dados = await lerJson(resposta);
    const detalhe =
      typeof dados === "object" && dados !== null && "detail" in dados ? dados.detail : undefined;
    if (resposta.status === 401 && notificar401) aoNaoAutenticado?.();
    throw new ErroApi(resposta.status, detalhe);
  }

  const dados = resposta.status === 204 ? undefined : await lerJson(resposta);
  const resultado = esquema.safeParse(dados);
  if (!resultado.success) throw new ErroRespostaInvalida();
  return resultado.data;
}
