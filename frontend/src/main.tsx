import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./estilos.css";

const raiz = document.getElementById("raiz");
if (!raiz) throw new Error("Elemento raiz ausente.");

createRoot(raiz).render(<StrictMode />);
