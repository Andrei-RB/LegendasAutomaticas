import { z } from "zod";
import type { components } from "./esquema";

type UsuarioApi = components["schemas"]["UsuarioSaida"];
type LoginApi = components["schemas"]["LoginEntrada"];

export const esquemaUsuario = z.object({
  id: z.string().uuid(),
  email: z.string(),
  nome_usuario: z.string(),
  idioma: z.string(),
}) satisfies z.ZodType<UsuarioApi>;

export type Usuario = z.infer<typeof esquemaUsuario>;

// As mensagens são chaves do catálogo de i18n, traduzidas na exibição.
export const esquemaLogin = z.object({
  email: z
    .string()
    .trim()
    .toLowerCase()
    .min(1, "validacao.email_invalido")
    .pipe(z.email("validacao.email_invalido")),
  senha: z.string().min(1, "validacao.senha_obrigatoria"),
}) satisfies z.ZodType<LoginApi, unknown>;

export type DadosLogin = z.infer<typeof esquemaLogin>;
