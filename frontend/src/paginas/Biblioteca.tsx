import { useTranslation } from "react-i18next";

export function Biblioteca() {
  const { t } = useTranslation();
  return (
    <section>
      <h1 className="text-2xl font-semibold tracking-tight">{t("paginas.biblioteca.titulo")}</h1>
      <p className="mt-4 text-muted-foreground">{t("paginas.biblioteca.vazio")}</p>
    </section>
  );
}
