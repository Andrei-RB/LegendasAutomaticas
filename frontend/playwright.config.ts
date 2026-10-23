import { defineConfig, devices } from "@playwright/test";

const url = process.env.E2E_URL ?? "http://127.0.0.1:8080";

export default defineConfig({
  testDir: "e2e",
  globalSetup: "./e2e/preparar.ts",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: { baseURL: url, locale: "pt-BR", trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
