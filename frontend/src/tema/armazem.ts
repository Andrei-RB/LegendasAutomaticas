import { create } from "zustand";
import { persist } from "zustand/middleware";
import { z } from "zod";

export type Tema = "escuro" | "claro";

const esquemaPersistido = z.object({ tema: z.enum(["escuro", "claro"]) });

interface EstadoTema {
  tema: Tema;
  definirTema: (tema: Tema) => void;
  alternarTema: () => void;
}

function aplicarTema(tema: Tema): void {
  document.documentElement.classList.toggle("dark", tema === "escuro");
}

export const useTema = create<EstadoTema>()(
  persist(
    (definir, obter) => ({
      tema: "escuro",
      definirTema: (tema) => {
        aplicarTema(tema);
        definir({ tema });
      },
      alternarTema: () => obter().definirTema(obter().tema === "escuro" ? "claro" : "escuro"),
    }),
    {
      name: "viraliza.tema",
      version: 0,
      partialize: (estado) => ({ tema: estado.tema }),
      // Valor salvo fora do esperado volta ao padrão escuro.
      merge: (salvo, atual) => {
        const lido = esquemaPersistido.safeParse(salvo);
        return { ...atual, tema: lido.success ? lido.data.tema : atual.tema };
      },
      onRehydrateStorage: () => (estado) => aplicarTema(estado?.tema ?? "escuro"),
    },
  ),
);
