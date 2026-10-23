import { vi } from "vitest";

export const usuarioExemplo = {
  id: "6f1c2d3e-4a5b-4c6d-8e7f-0a1b2c3d4e5f",
  email: "usuario@exemplo.test",
  nome_usuario: "usuario",
  idioma: "pt-BR",
};

export function respostaJson(corpo: unknown, status = 200): Response {
  if (status === 204) return new Response(null, { status });
  return new Response(JSON.stringify(corpo), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export function respostaTexto(texto: string, status: number): Response {
  return new Response(texto, { status, headers: { "Content-Type": "text/plain" } });
}

export interface RequisicaoSimulada {
  metodo: string;
  caminho: string;
  corpo: unknown;
  cabecalhos: Headers;
  init: RequestInit | undefined;
}

export type ManipuladorFetch = (req: RequisicaoSimulada) => Response | Promise<Response>;

function urlDe(entrada: RequestInfo | URL): string {
  if (typeof entrada === "string") return entrada;
  if (entrada instanceof URL) return entrada.href;
  return entrada.url;
}

// Substitui o fetch global; o manipulador pode lançar para simular falha de rede.
export function simularFetch(manipulador: ManipuladorFetch) {
  const requisicoes: RequisicaoSimulada[] = [];
  const mock = vi.fn(async (entrada: RequestInfo | URL, init?: RequestInit) => {
    const req: RequisicaoSimulada = {
      metodo: (init?.method ?? "GET").toUpperCase(),
      caminho: urlDe(entrada),
      corpo: typeof init?.body === "string" ? JSON.parse(init.body) : undefined,
      cabecalhos: new Headers(init?.headers),
      init,
    };
    requisicoes.push(req);
    return manipulador(req);
  });
  vi.stubGlobal("fetch", mock);
  return {
    fetch: mock,
    requisicoes,
    contar: (metodo: string, caminho: string) =>
      requisicoes.filter((r) => r.metodo === metodo && r.caminho === caminho).length,
  };
}

export function executarTemaInicial(codigo: string): void {
  new Function(codigo)();
}
