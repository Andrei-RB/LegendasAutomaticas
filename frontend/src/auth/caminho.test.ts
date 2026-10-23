import { caminhoSeguro } from "@/auth/caminho";

describe("caminhoSeguro: aceita caminhos internos", () => {
  it.each(["/", "/painel", "/painel?a=1", "/config#secao", "/a/b/c?x=1&y=2"])(
    "aceita %j",
    (valor) => {
      expect(caminhoSeguro(valor)).toBe(valor);
    },
  );
});

describe("caminhoSeguro: bloqueia redirecionamento aberto", () => {
  it.each([
    ["URL absoluta https", "https://x.test"],
    ["URL absoluta http com caminho", "http://x.test/a"],
    ["protocolo relativo", "//x.test"],
    ["protocolo relativo com caminho", "//x.test/painel"],
    ["barra invertida após barra", "/\\x.test"],
    ["barra invertida inicial", "\\x.test"],
    ["esquema javascript", "javascript:alert(1)"],
    ["esquema data", "data:text/html,x"],
    ["vazio", ""],
    ["sem barra inicial", "painel"],
    ["espaço antes da barra", " /painel"],
    ["URL embutida no parâmetro", "/sair?para=https://x.test"],
    ["quebra de linha", "/painel\nLocation: https://x.test"],
    ["tabulação", "/\t/x.test"],
    ["caractere nulo", "/painel\u0000"],
    ["retorno de carro", "/painel\r"],
  ])("rejeita %s", (_nome, valor) => {
    expect(caminhoSeguro(valor)).toBe("/");
  });

  it.each([null, undefined])("devolve o padrão para %s", (valor) => {
    expect(caminhoSeguro(valor)).toBe("/");
  });

  it("usa o padrão informado quando o valor é inseguro", () => {
    expect(caminhoSeguro("//x.test", "/painel")).toBe("/painel");
    expect(caminhoSeguro(null, "/config")).toBe("/config");
    expect(caminhoSeguro("https://x.test", "/painel")).toBe("/painel");
  });

  it("não usa o padrão quando o valor é seguro", () => {
    expect(caminhoSeguro("/config", "/painel")).toBe("/config");
  });
});
