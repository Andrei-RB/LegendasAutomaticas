import fs from "node:fs";
import path from "node:path";
import ts from "typescript";

const ATRIBUTOS = new Set([
  "placeholder",
  "title",
  "alt",
  "aria-label",
  "aria-description",
  "label",
  "aria-placeholder",
]);
const TEM_LETRA = /\p{L}/u;

interface Achado {
  linha: number;
  trecho: string;
}

function textoLiteral(no: ts.Node | undefined): string | null {
  if (!no) return null;
  if (ts.isStringLiteral(no) || ts.isNoSubstitutionTemplateLiteral(no)) return no.text;
  if (ts.isJsxExpression(no)) return textoLiteral(no.expression);
  return null;
}

function acharTextosLiterais(codigo: string, nome = "memoria.tsx"): Achado[] {
  const fonte = ts.createSourceFile(nome, codigo, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const achados: Achado[] = [];
  const registrar = (posicao: number, trecho: string) => {
    const { line } = fonte.getLineAndCharacterOfPosition(posicao);
    achados.push({ linha: line + 1, trecho: trecho.trim().slice(0, 40) });
  };

  const visitar = (no: ts.Node): void => {
    if (ts.isJsxText(no)) {
      const letra = TEM_LETRA.exec(no.text);
      if (letra) registrar(no.pos + letra.index, no.text);
    } else if (ts.isJsxAttribute(no)) {
      const rotulo = ts.isIdentifier(no.name) ? no.name.text : no.name.getText(fonte);
      const valor = textoLiteral(no.initializer);
      if (ATRIBUTOS.has(rotulo) && valor !== null && TEM_LETRA.test(valor)) {
        registrar(no.getStart(fonte), `${rotulo}="${valor}"`);
      }
    } else if (ts.isJsxExpression(no) && (ts.isJsxElement(no.parent) || ts.isJsxFragment(no.parent))) {
      const valor = textoLiteral(no);
      if (valor !== null && TEM_LETRA.test(valor)) registrar(no.getStart(fonte), valor);
    }
    ts.forEachChild(no, visitar);
  };
  visitar(fonte);
  return achados;
}

function listarTsx(raiz: string): string[] {
  return (fs.readdirSync(raiz, { recursive: true }) as string[])
    .map((relativo) => relativo.replaceAll("\\", "/"))
    .filter((relativo) => relativo.endsWith(".tsx") && !relativo.endsWith(".test.tsx"))
    .filter((relativo) => !relativo.startsWith("testes/"))
    .sort();
}

const RAIZ_SRC = path.resolve(import.meta.dirname, "..");

describe("detector de textos literais", () => {
  it("encontra texto literal em JSX, inclusive com acento", () => {
    expect(acharTextosLiterais("const a = <p>Olá mundo</p>;")).toHaveLength(1);
    expect(acharTextosLiterais("const a = <p>Ação</p>;")).toHaveLength(1);
  });

  it("encontra texto literal em expressão string dentro do JSX", () => {
    expect(acharTextosLiterais('const a = <p>{"Salvar"}</p>;')).toHaveLength(1);
  });

  it.each(["placeholder", "title", "alt", "aria-label", "aria-description", "label", "aria-placeholder"])(
    "encontra atributo %s com string literal",
    (atributo) => {
      expect(acharTextosLiterais(`const a = <input ${atributo}="Buscar vídeo" />;`)).toHaveLength(
        1,
      );
    },
  );

  it("informa a linha do achado", () => {
    const achados = acharTextosLiterais("const a = (\n  <div>\n    <p>Texto</p>\n  </div>\n);");
    expect(achados.map((a) => a.linha)).toEqual([3]);
  });

  it("não reclama de className, type, data-* e valores sem letras", () => {
    const codigo = [
      'const a = <div className="flex gap-2" data-testid="caixa" id="x">',
      '  <input type="email" name="email" autoComplete="off" />',
      "  <p>{t('rotulo')}</p>",
      '  <span>{" "}</span>',
      "  <span>-</span>",
      "  <span>1 / 2</span>",
      '  <img alt="" src="/icone.svg" />',
      "  <input placeholder={t('campo')} aria-label={rotulo} />",
      "</div>;",
    ].join("\n");
    expect(acharTextosLiterais(codigo)).toEqual([]);
  });
});

describe("textos fixos em componentes", () => {
  it("há arquivos .tsx de produção para inspecionar", () => {
    expect(listarTsx(RAIZ_SRC).length).toBeGreaterThan(0);
  });

  it("nenhum .tsx de produção contém texto literal visível", () => {
    const falhas: string[] = [];
    for (const relativo of listarTsx(RAIZ_SRC)) {
      const codigo = fs.readFileSync(path.join(RAIZ_SRC, relativo), "utf-8");
      for (const achado of acharTextosLiterais(codigo, relativo)) {
        falhas.push(`src/${relativo}:${achado.linha} ${achado.trecho}`);
      }
    }
    expect(falhas).toEqual([]);
  });
});
