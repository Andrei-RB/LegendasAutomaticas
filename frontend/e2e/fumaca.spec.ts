import { expect, test } from "@playwright/test";

const email = process.env.E2E_EMAIL;
const senha = process.env.E2E_SENHA;

test.describe("fumaça: login, navegação e logout", () => {
  test.skip(!email || !senha, "Defina E2E_EMAIL e E2E_SENHA.");

  test("rota protegida redireciona para o login", async ({ page }) => {
    await page.goto("/painel");
    await expect(page).toHaveURL(/\/entrar\?de=%2Fpainel$/);
    await expect(page.getByRole("heading", { name: "Entrar" })).toBeVisible();
  });

  test("senha incorreta mostra erro e permanece no login", async ({ page }) => {
    await page.goto("/entrar");
    await page.getByLabel("E-mail").fill(email ?? "");
    await page.getByLabel("Senha").fill(`${senha}-incorreta`);
    await page.getByRole("button", { name: "Entrar" }).click();
    await expect(page.getByRole("alert")).toHaveText("E-mail ou senha incorretos.");
    await expect(page).toHaveURL(/\/entrar/);
  });

  test("login, navegação e logout", async ({ page }) => {
    await page.goto("/painel");
    await page.getByLabel("E-mail").fill(email ?? "");
    await page.getByLabel("Senha").fill(senha ?? "");
    await page.getByRole("button", { name: "Entrar" }).click();

    await expect(page).toHaveURL(/\/painel$/);
    await expect(page.getByRole("heading", { name: "Painel" })).toBeVisible();

    await page.getByRole("link", { name: "Configurações" }).click();
    await expect(page).toHaveURL(/\/config$/);
    await expect(page.getByRole("heading", { name: "Configurações" })).toBeVisible();

    await page.getByRole("button", { name: "Sair" }).click();
    await expect(page).toHaveURL(/\/entrar$/);

    await page.goto("/config");
    await expect(page).toHaveURL(/\/entrar\?de=%2Fconfig$/);
  });

  test("a interface é servida com cabeçalhos de segurança", async ({ request }) => {
    const resposta = await request.get("/");
    const cabecalhos = resposta.headers();
    expect(cabecalhos["content-security-policy"]).toContain("default-src 'none'");
    expect(cabecalhos["x-content-type-options"]).toBe("nosniff");
    expect(cabecalhos["x-frame-options"]).toBe("DENY");
    expect(cabecalhos["referrer-policy"]).toBe("no-referrer");
  });
});
