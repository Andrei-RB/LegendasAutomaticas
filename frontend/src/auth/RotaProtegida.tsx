import { useTranslation } from "react-i18next";
import { Navigate, Outlet, useLocation } from "react-router";
import { Botao } from "@/componentes/ui/botao";
import { useSessao } from "./useSessao";

export function RotaProtegida() {
  const { t } = useTranslation();
  const { pathname, search } = useLocation();
  const { usuario, carregando, erro, recarregando, tentarDeNovo } = useSessao();

  if (carregando) {
    return (
      <p role="status" className="p-6 text-muted-foreground">
        {t("sessao.carregando")}
      </p>
    );
  }
  if (erro) {
    return (
      <div role="alert" className="flex flex-col items-start gap-3 p-6">
        <p>{t("sessao.erro")}</p>
        <Botao variante="contorno" disabled={recarregando} onClick={tentarDeNovo}>
          {t("acoes.tentarDeNovo")}
        </Botao>
      </div>
    );
  }
  if (!usuario) {
    return <Navigate to={`/entrar?de=${encodeURIComponent(pathname + search)}`} replace />;
  }
  return <Outlet />;
}
