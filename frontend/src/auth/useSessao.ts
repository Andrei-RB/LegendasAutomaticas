import { useQuery } from "@tanstack/react-query";
import { obterSessao } from "@/api/auth";
import { ErroApi } from "@/api/erros";
import type { Usuario } from "@/api/esquemas";

export const CHAVE_SESSAO = ["sessao"] as const;

export function useSessao() {
  const consulta = useQuery<Usuario | null, ErroApi>({
    queryKey: CHAVE_SESSAO,
    queryFn: async () => {
      try {
        return await obterSessao();
      } catch (erro) {
        if (erro instanceof ErroApi && erro.status === 401) return null;
        throw erro;
      }
    },
    retry: false,
    staleTime: 5 * 60_000,
  });
  return {
    usuario: consulta.data,
    carregando: consulta.isPending,
    erro: consulta.error,
    recarregando: consulta.isFetching,
    tentarDeNovo: () => void consulta.refetch(),
  };
}
