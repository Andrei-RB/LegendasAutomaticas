import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(import.meta.dirname, "src") } },
  server: {
    host: "127.0.0.1",
    // Em desenvolvimento a API é encaminhada para manter cookie e origem no mesmo domínio.
    proxy: { "/api": { target: "http://127.0.0.1:8000", changeOrigin: false } },
  },
  build: { sourcemap: false, target: "es2023" },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["src/testes/preparar.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    css: false,
  },
});
