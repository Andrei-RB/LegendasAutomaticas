import { useMutation } from "@tanstack/react-query";
import { LogOut } from "lucide-react";
import { useTranslation } from "react-i18next";
import { NavLink, Outlet, useNavigate } from "react-router";
import { sair } from "@/api/auth";
import { ErroApi } from "@/api/erros";
import { chaveErro } from "@/api/mensagemErro";
import { useSessao } from "@/auth/useSessao";
import { cn } from "@/lib/utils";
import { AlternarTema } from "./AlternarTema";
import { Botao } from "./ui/botao";

const itens = [
  { para: "/", chave: "menu.biblioteca", fim: true },
  { para: "/painel", chave: "menu.painel", fim: false },
  { para: "/config", chave: "menu.config", fim: false },
] as const;

export function Layout() {
  const { t } = useTranslation();
  const { usuario } = useSessao();
  const navegar = useNavigate();
  const saida = useMutation({
    mutationFn: sair,
    onSuccess: () => navegar("/entrar", { replace: true }),
    // 401 e 503 já deixam o cookie inválido ou apagado; as demais falhas mantêm a sessão.
    onError: (erro) => {
      if (erro instanceof ErroApi && (erro.status === 401 || erro.status === 503)) {
        return navegar("/entrar", { replace: true });
      }
    },
  });

  return (
    <div className="min-h-dvh md:grid md:grid-cols-[15rem_1fr]">
      <aside className="flex flex-wrap items-center gap-3 border-b bg-card px-4 py-3 md:sticky md:top-0 md:h-dvh md:flex-col md:items-stretch md:border-r md:border-b-0 md:py-5">
        <span className="text-lg font-semibold tracking-tight text-primary md:px-2">
          {t("marca")}
        </span>
        <nav aria-label={t("menu.navegacao")} className="flex gap-1 md:flex-1 md:flex-col">
          {itens.map((item) => (
            <NavLink
              key={item.para}
              to={item.para}
              end={item.fim}
              className={({ isActive }) =>
                cn(
                  "rounded-md px-3 py-2 text-sm font-medium hover:bg-muted",
                  isActive && "bg-muted text-primary",
                )
              }
            >
              {t(item.chave)}
            </NavLink>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-1 md:ml-0 md:justify-between md:border-t md:pt-3">
          <span className="hidden truncate px-2 text-sm text-muted-foreground md:inline">
            {usuario?.nome_usuario}
          </span>
          <div className="flex items-center">
            <AlternarTema />
            <Botao
              variante="fantasma"
              tamanho="icone"
              aria-label={t("acoes.sair")}
              title={t("acoes.sair")}
              disabled={saida.isPending}
              onClick={() => saida.mutate()}
            >
              <LogOut aria-hidden="true" className="size-5" />
            </Botao>
          </div>
        </div>
      </aside>
      <main className="mx-auto w-full max-w-6xl p-4 md:p-8">
        {saida.isError && (
          <p role="alert" className="mb-4 text-sm text-destructive">
            {t(chaveErro(saida.error))}
          </p>
        )}
        <Outlet />
      </main>
    </div>
  );
}
