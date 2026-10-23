import { useTranslation } from "react-i18next";
import { Link } from "react-router";

export function NaoEncontrada() {
  const { t } = useTranslation();
  return (
    <section>
      <h1 className="text-2xl font-semibold tracking-tight">
        {t("paginas.nao_encontrada.titulo")}
      </h1>
      <p className="mt-4 text-muted-foreground">{t("paginas.nao_encontrada.descricao")}</p>
      <Link to="/" className="mt-4 inline-block text-primary underline underline-offset-4">
        {t("acoes.voltarInicio")}
      </Link>
    </section>
  );
}
