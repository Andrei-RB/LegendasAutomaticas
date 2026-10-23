import fs from "node:fs";
import path from "node:path";

const css = fs.readFileSync(path.resolve(import.meta.dirname, "../estilos.css"), "utf-8");

type Tokens = Record<string, [number, number, number]>;

function bloco(seletor: string): string {
  const inicio = css.indexOf(`${seletor} {`);
  return css.slice(inicio, css.indexOf("}", inicio));
}

function tokens(seletor: string): Tokens {
  const saida: Tokens = {};
  for (const m of bloco(seletor).matchAll(/--([\w-]+):\s*oklch\(([\d.]+)\s+([\d.]+)\s+([\d.]+)\)/g)) {
    saida[m[1]!] = [Number(m[2]), Number(m[3]), Number(m[4])];
  }
  return saida;
}

function luminancia([l, c, h]: [number, number, number]): number {
  const a = c * Math.cos((h * Math.PI) / 180);
  const b = c * Math.sin((h * Math.PI) / 180);
  const l_ = (l + 0.3963377774 * a + 0.2158037573 * b) ** 3;
  const m_ = (l - 0.1055613458 * a - 0.0638541728 * b) ** 3;
  const s_ = (l - 0.0894841775 * a - 1.291485548 * b) ** 3;
  const r = 4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_;
  const g = -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_;
  const bl = -0.0041960863 * l_ - 0.7034186147 * m_ + 1.707614701 * s_;
  const canal = (x: number) => Math.min(1, Math.max(0, x));
  return 0.2126 * canal(r) + 0.7152 * canal(g) + 0.0722 * canal(bl);
}

function razao(a: [number, number, number], b: [number, number, number]): number {
  const [x, y] = [luminancia(a), luminancia(b)];
  return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
}

const temas = { claro: tokens(":root"), escuro: tokens(".dark") };

describe.each(Object.entries(temas))("contraste WCAG 2.2 AA (%s)", (_, t) => {
  it("borda de campo tem 3:1 contra o cartão e contra o fundo", () => {
    expect(razao(t["input"]!, t["card"]!)).toBeGreaterThanOrEqual(3);
    expect(razao(t["input"]!, t["background"]!)).toBeGreaterThanOrEqual(3);
  });

  it("anel de foco tem 3:1 contra o fundo e contra o cartão", () => {
    expect(razao(t["ring"]!, t["background"]!)).toBeGreaterThanOrEqual(3);
    expect(razao(t["ring"]!, t["card"]!)).toBeGreaterThanOrEqual(3);
  });

  it.each([
    ["foreground", "background"],
    ["card-foreground", "card"],
    ["muted-foreground", "background"],
    ["muted-foreground", "muted"],
    ["primary-foreground", "primary"],
    ["destructive-foreground", "destructive"],
    ["primary", "background"],
    ["destructive", "background"],
  ])("texto %s sobre %s tem 4,5:1", (frente, fundo) => {
    expect(razao(t[frente]!, t[fundo]!)).toBeGreaterThanOrEqual(4.5);
  });
});
