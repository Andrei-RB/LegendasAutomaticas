import { z } from "zod";
import { requisitar } from "./cliente";
import { type DadosLogin, type Usuario, esquemaUsuario } from "./esquemas";

export function entrar(dados: DadosLogin): Promise<Usuario> {
  return requisitar("/auth/login", {
    metodo: "POST",
    corpo: dados,
    esquema: esquemaUsuario,
    notificar401: false,
  });
}

export function sair(): Promise<void> {
  return requisitar("/auth/logout", { metodo: "POST", esquema: z.void() });
}

export function obterSessao(): Promise<Usuario> {
  return requisitar("/auth/eu", { esquema: esquemaUsuario, notificar401: false });
}
