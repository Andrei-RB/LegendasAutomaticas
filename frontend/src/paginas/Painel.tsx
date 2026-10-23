import { useTranslation } from "react-i18next";

export function Painel() {
  const { t } = useTranslation();
  return (
    <section>
      <h1 className="text-2xl font-semibold tracking-tight">{t("paginas.painel.titulo")}</h1>
      <p className="mt-4 text-muted-foreground">{t("paginas.painel.descricao")}</p>
    </section>
  );
}
