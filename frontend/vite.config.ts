import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(import.meta.dirname, "src") } },
  server: {
    host: "127.0.0.1",
    // A API aceita a origem do contêiner frontend (CORS_ORIGINS); o proxy a repassa no lugar de :5173.
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        configure: (proxy) => {
          proxy.on("proxyReq", (requisicao) => requisicao.setHeader("Origin", "http://127.0.0.1:8080"));
        },
      },
    },
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
