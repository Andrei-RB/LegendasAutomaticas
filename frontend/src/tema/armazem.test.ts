import fs from "node:fs";
import path from "node:path";
import { useTema } from "@/tema/armazem";
import { executarTemaInicial } from "@/testes/auxiliares";

const CHAVE = "viraliza.tema";
const scriptInicial = fs.readFileSync(
  path.resolve(import.meta.dirname, "../../public/tema-inicial.js"),
  "utf-8",
);

function temClasseEscura(): boolean {
  return document.documentElement.classList.contains("dark");
}

async function importarLimpo() {
  vi.resetModules();
  return (await import("@/tema/armazem")).useTema;
}

beforeEach(() => {
  useTema.getState().definirTema("escuro");
  localStorage.removeItem(CHAVE);
});

describe("useTema: estado", () => {
  it("o padrão é escuro quando não há valor salvo", async () => {
    localStorage.clear();
    const armazem = await importarLimpo();
    expect(armazem.getState().tema).toBe("escuro");
  });

  it("definirTema('claro') remove a classe dark", () => {
    useTema.getState().definirTema("claro");
    expect(useTema.getState().tema).toBe("claro");
    expect(temClasseEscura()).toBe(false);
  });

  it("definirTema('escuro') adiciona a classe dark", () => {
    useTema.getState().definirTema("claro");
    useTema.getState().definirTema("escuro");
    expect(useTema.getState().tema).toBe("escuro");
    expect(temClasseEscura()).toBe(true);
  });

  it("definirTema repetido é idempotente", () => {
    useTema.getState().definirTema("claro");
    useTema.getState().definirTema("claro");
    expect(temClasseEscura()).toBe(false);
    useTema.getState().definirTema("escuro");
    useTema.getState().definirTema("escuro");
    expect(temClasseEscura()).toBe(true);
    expect(document.documentElement.className.split(" ").filter((c) => c === "dark")).toHaveLength(
      1,
    );
  });

  it("alternarTema troca entre escuro e claro e sincroniza a classe", () => {
    useTema.getState().alternarTema();
    expect(useTema.getState().tema).toBe("claro");
    expect(temClasseEscura()).toBe(false);
    useTema.getState().alternarTema();
    expect(useTema.getState().tema).toBe("escuro");
    expect(temClasseEscura()).toBe(true);
  });
});

describe("useTema: persistência", () => {
  it("salva {state:{tema}, version:0} em viraliza.tema", () => {
    useTema.getState().definirTema("claro");
    expect(JSON.parse(localStorage.getItem(CHAVE) ?? "null")).toEqual({
      state: { tema: "claro" },
      version: 0,
    });
  });

  it("relê o valor salvo após rehydrate", async () => {
    localStorage.setItem(CHAVE, JSON.stringify({ state: { tema: "claro" }, version: 0 }));
    await useTema.persist.rehydrate();
    expect(useTema.getState().tema).toBe("claro");
  });

  it("carrega 'claro' salvo ao iniciar o módulo", async () => {
    localStorage.setItem(CHAVE, JSON.stringify({ state: { tema: "claro" }, version: 0 }));
    const armazem = await importarLimpo();
    expect(armazem.getState().tema).toBe("claro");
  });

  it.each([
    ["tema desconhecido", JSON.stringify({ state: { tema: "roxo" }, version: 0 })],
    ["tema numérico", JSON.stringify({ state: { tema: 1 }, version: 0 })],
    ["sem estado", JSON.stringify({ version: 0 })],
    ["texto puro", "lixo"],
    ["JSON quebrado", "{state:"],
  ])("valor inválido (%s) resulta em escuro", async (_nome, bruto) => {
    localStorage.setItem(CHAVE, bruto);
    const armazem = await importarLimpo();
    expect(armazem.getState().tema).toBe("escuro");
  });

  it("o script inicial concorda com o valor persistido", () => {
    useTema.getState().definirTema("claro");
    document.documentElement.classList.add("dark");
    executarTemaInicial(scriptInicial);
    expect(temClasseEscura()).toBe(false);

    useTema.getState().definirTema("escuro");
    document.documentElement.classList.remove("dark");
    executarTemaInicial(scriptInicial);
    expect(temClasseEscura()).toBe(true);
  });
});
