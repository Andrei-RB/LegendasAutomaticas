import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider, createBrowserRouter } from "react-router";
import { Provedores, criarClienteConsulta } from "./app/provedores";
import { rotas } from "./app/rotas";
import "./i18n";
import "./estilos.css";

const raiz = document.getElementById("raiz");
if (!raiz) throw new Error("Elemento raiz ausente.");

createRoot(raiz).render(
  <StrictMode>
    <Provedores cliente={criarClienteConsulta()}>
      <RouterProvider router={createBrowserRouter(rotas)} />
    </Provedores>
  </StrictMode>,
);
