import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { definirAoNaoAutenticado } from "@/api/cliente";
import { CHAVE_SESSAO } from "@/auth/useSessao";

export function criarClienteConsulta(): QueryClient {
  const cliente = new QueryClient({
    defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
  });
  // Um 401 em qualquer requisição invalida a sessão e a guarda leva ao login.
  definirAoNaoAutenticado(() => cliente.setQueryData(CHAVE_SESSAO, null));
  return cliente;
}

export function Provedores({ cliente, children }: { cliente: QueryClient; children: ReactNode }) {
  return <QueryClientProvider client={cliente}>{children}</QueryClientProvider>;
}
