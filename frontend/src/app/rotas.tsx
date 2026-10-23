import type { RouteObject } from "react-router";
import { RotaProtegida } from "@/auth/RotaProtegida";
import { Layout } from "@/componentes/Layout";
import { Biblioteca } from "@/paginas/Biblioteca";
import { Config } from "@/paginas/Config";
import { Entrar } from "@/paginas/Entrar";
import { NaoEncontrada } from "@/paginas/NaoEncontrada";
import { Painel } from "@/paginas/Painel";

export const rotas: RouteObject[] = [
  { path: "/entrar", element: <Entrar /> },
  {
    element: <RotaProtegida />,
    children: [
      {
        element: <Layout />,
        children: [
          { index: true, element: <Biblioteca /> },
          { path: "painel", element: <Painel /> },
          { path: "config", element: <Config /> },
          { path: "*", element: <NaoEncontrada /> },
        ],
      },
    ],
  },
];
