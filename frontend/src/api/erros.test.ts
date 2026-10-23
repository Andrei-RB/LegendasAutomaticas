import { ErroApi } from "@/api/erros";

describe("ErroApi", () => {
  it("é um Error com status e detalhe", () => {
    const erro = new ErroApi(404, "Não encontrado.");
    expect(erro).toBeInstanceOf(Error);
    expect(erro).toBeInstanceOf(ErroApi);
    expect(erro.status).toBe(404);
    expect(erro.detalhe).toBe("Não encontrado.");
  });

  it("aceita detalhe estruturado", () => {
    const detalhe = [{ loc: ["body", "email"], msg: "inválido" }];
    expect(new ErroApi(422, detalhe).detalhe).toEqual(detalhe);
  });
});
