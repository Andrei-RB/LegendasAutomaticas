import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import { catalogo } from "./pt-BR";

declare module "i18next" {
  interface CustomTypeOptions {
    defaultNS: "translation";
    resources: { translation: typeof catalogo };
  }
}

void i18n.use(initReactI18next).init({
  lng: "pt-BR",
  fallbackLng: "pt-BR",
  resources: { "pt-BR": { translation: catalogo } },
  interpolation: { escapeValue: false },
  returnNull: false,
});

export default i18n;
