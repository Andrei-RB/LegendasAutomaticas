import { request } from "@playwright/test";

// Cria o usuário do teste; 403 (cadastro fechado) e 409 (já existe) são esperados em bancos usados.
export default async function preparar(): Promise<void> {
  const email = process.env.E2E_EMAIL;
  const senha = process.env.E2E_SENHA;
  if (!email || !senha) return;
  const url = process.env.E2E_URL ?? "http://127.0.0.1:8080";
  const contexto = await request.newContext({ baseURL: url, extraHTTPHeaders: { Origin: url } });
  const resposta = await contexto.post("/api/v1/auth/cadastro", {
    data: { email, senha, nome_usuario: "usuario-e2e" },
  });
  await contexto.dispose();
  if (![201, 403, 409].includes(resposta.status())) {
    throw new Error(`Falha ao preparar o usuário de teste: HTTP ${resposta.status()}`);
  }
}
