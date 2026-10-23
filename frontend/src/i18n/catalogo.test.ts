import type { i18n as InstanciaI18n } from "i18next";
import * as modulo from "@/i18n";
import { catalogo } from "@/i18n/pt-BR";

const exportados = modulo as unknown as Record<string, unknown>;
const i18n = (exportados["i18n"] ?? exportados["default"]) as InstanciaI18n;

function achatar(obj: unknown, prefixo = ""): Record<string, unknown> {
  const saida: Record<string, unknown> = {};
  if (typeof obj !== "object" || obj === null || Array.isArray(obj)) return saida;
  for (const [chave, valor] of Object.entries(obj)) {
    const caminho = prefixo ? `${prefixo}.${chave}` : chave;
    if (typeof valor === "object" && valor !== null && !Array.isArray(valor)) {
      Object.assign(saida, achatar(valor, caminho));
    } else {
      saida[caminho] = valor;
    }
  }
  return saida;
}

const entradas = achatar(catalogo);

describe("catálogo pt-BR", () => {
  it("não está vazio", () => {
    expect(Object.keys(entradas).length).toBeGreaterThan(0);
  });

  it("define as mensagens de validação do login", () => {
    expect(entradas["validacao.email_invalido"]).toBe("Informe um e-mail válido.");
    expect(entradas["validacao.senha_obrigatoria"]).toBe("Informe a senha.");
  });

  it("todo valor é string não vazia", () => {
    const invalidas = Object.entries(entradas)
      .filter(([, valor]) => typeof valor !== "string" || valor.trim() === "")
      .map(([chave]) => chave);
    expect(invalidas).toEqual([]);
  });
});

describe("i18n", () => {
  it("traduz validacao.email_invalido em pt-BR", () => {
    expect(i18n.t("validacao.email_invalido")).toBe("Informe um e-mail válido.");
  });

  it("traduz validacao.senha_obrigatoria em pt-BR", () => {
    expect(i18n.t("validacao.senha_obrigatoria")).toBe("Informe a senha.");
  });
});
