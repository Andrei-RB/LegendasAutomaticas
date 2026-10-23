import { Moon, Sun } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useTema } from "@/tema/armazem";
import { Botao } from "./ui/botao";

export function AlternarTema() {
  const { t } = useTranslation();
  const { tema, alternarTema } = useTema();
  const Icone = tema === "escuro" ? Sun : Moon;
  return (
    <Botao
      variante="fantasma"
      tamanho="icone"
      aria-label={t("acoes.alternarTema")}
      title={tema === "escuro" ? t("tema.claro") : t("tema.escuro")}
      onClick={alternarTema}
    >
      <Icone aria-hidden="true" className="size-5" />
    </Botao>
  );
}
