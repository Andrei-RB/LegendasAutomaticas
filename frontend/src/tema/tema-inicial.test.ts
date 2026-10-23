import fs from "node:fs";
import path from "node:path";
import { executarTemaInicial } from "@/testes/auxiliares";

const CHAVE = "viraliza.tema";
const codigo = fs.readFileSync(
  path.resolve(import.meta.dirname, "../../public/tema-inicial.js"),
  "utf-8",
);
const classes = document.documentElement.classList;

function salvar(valor: string): void {
  localStorage.setItem(CHAVE, valor);
}

beforeEach(() => {
  classes.remove("dark");
});

describe("public/tema-inicial.js", () => {
  it("sem valor salvo aplica o escuro", () => {
    executarTemaInicial(codigo);
    expect(classes.contains("dark")).toBe(true);
  });

  it("tema escuro salvo aplica a classe dark", () => {
    salvar(JSON.stringify({ state: { tema: "escuro" }, version: 0 }));
    executarTemaInicial(codigo);
    expect(classes.contains("dark")).toBe(true);
  });

  it("tema claro salvo remove a classe dark", () => {
    classes.add("dark");
    salvar(JSON.stringify({ state: { tema: "claro" }, version: 0 }));
    executarTemaInicial(codigo);
    expect(classes.contains("dark")).toBe(false);
  });

  it.each(["lixo", "{state:", JSON.stringify({ state: { tema: "roxo" }, version: 0 }), "null"])(
    "valor inválido %j cai no escuro",
    (bruto) => {
      salvar(bruto);
      executarTemaInicial(codigo);
      expect(classes.contains("dark")).toBe(true);
    },
  );
});
