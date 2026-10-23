import { z } from "zod";
import { definirAoNaoAutenticado, requisitar } from "@/api/cliente";
import { ErroApi, ErroRespostaInvalida } from "@/api/erros";
import { respostaJson, respostaTexto, simularFetch } from "@/testes/auxiliares";

const esquemaItem = z.object({ id: z.number(), nome: z.string() });

afterEach(() => {
  definirAoNaoAutenticado(null);
  vi.unstubAllGlobals();
});

describe("requisitar: requisição", () => {
  it("usa GET, prefixo /api/v1, credenciais e Accept JSON por padrão", async () => {
    const api = simularFetch(() => respostaJson({ id: 1, nome: "a" }));
    await requisitar("/itens/1", { esquema: esquemaItem });
    const req = api.requisicoes[0]!;
    expect(req.caminho).toBe("/api/v1/itens/1");
    expect(req.metodo).toBe("GET");
    expect(req.init?.credentials).toBe("same-origin");
    expect(req.cabecalhos.get("Accept")).toBe("application/json");
    expect(req.cabecalhos.has("Content-Type")).toBe(false);
    expect(req.init?.body).toBeUndefined();
  });

  it("envia corpo JSON com Content-Type apenas quando há corpo", async () => {
    const api = simularFetch(() => respostaJson({ id: 2, nome: "b" }));
    await requisitar("/itens", {
      esquema: esquemaItem,
      metodo: "POST",
      corpo: { nome: "ção ✓" },
    });
    const req = api.requisicoes[0]!;
    expect(req.metodo).toBe("POST");
    expect(req.cabecalhos.get("Content-Type")).toBe("application/json");
    expect(req.init?.body).toBe(JSON.stringify({ nome: "ção ✓" }));
  });

  it("POST sem corpo não define Content-Type", async () => {
    const api = simularFetch(() => respostaJson({ id: 3, nome: "c" }));
    await requisitar("/itens/acao", { esquema: esquemaItem, metodo: "POST" });
    expect(api.requisicoes[0]!.cabecalhos.has("Content-Type")).toBe(false);
  });
});

describe("requisitar: resposta", () => {
  it("devolve o JSON validado pelo esquema", async () => {
    simularFetch(() => respostaJson({ id: 1, nome: "a" }));
    await expect(requisitar("/itens/1", { esquema: esquemaItem })).resolves.toEqual({
      id: 1,
      nome: "a",
    });
  });

  it("204 devolve undefined com esquema void", async () => {
    simularFetch(() => respostaJson(undefined, 204));
    await expect(
      requisitar("/auth/logout", { esquema: z.void(), metodo: "POST" }),
    ).resolves.toBeUndefined();
  });

  it("JSON fora do esquema lança ErroRespostaInvalida (502)", async () => {
    simularFetch(() => respostaJson({ id: "texto" }));
    const erro = await requisitar("/itens/1", { esquema: esquemaItem }).catch((e: unknown) => e);
    expect(erro).toBeInstanceOf(ErroRespostaInvalida);
    expect(erro).toBeInstanceOf(ErroApi);
    expect((erro as ErroApi).status).toBe(502);
  });

  it("corpo 200 que não é JSON lança ErroRespostaInvalida", async () => {
    simularFetch(() => respostaTexto("<html>erro</html>", 200));
    await expect(requisitar("/itens/1", { esquema: esquemaItem })).rejects.toBeInstanceOf(
      ErroRespostaInvalida,
    );
  });
});

describe("requisitar: erros HTTP", () => {
  it("usa o campo detail como detalhe", async () => {
    simularFetch(() => respostaJson({ detail: "Cota esgotada." }, 429));
    const erro = await requisitar("/itens", { esquema: esquemaItem }).catch((e: unknown) => e);
    expect(erro).toBeInstanceOf(ErroApi);
    expect((erro as ErroApi).status).toBe(429);
    expect((erro as ErroApi).detalhe).toBe("Cota esgotada.");
  });

  it("preserva detail estruturado (422)", async () => {
    const detail = [{ loc: ["body", "nome"], msg: "obrigatório", type: "missing" }];
    simularFetch(() => respostaJson({ detail }, 422));
    const erro = await requisitar("/itens", { esquema: esquemaItem }).catch((e: unknown) => e);
    expect((erro as ErroApi).status).toBe(422);
    expect((erro as ErroApi).detalhe).toEqual(detail);
  });

  it("erro sem corpo JSON mantém o status", async () => {
    simularFetch(() => respostaTexto("falha interna", 500));
    const erro = await requisitar("/itens", { esquema: esquemaItem }).catch((e: unknown) => e);
    expect(erro).toBeInstanceOf(ErroApi);
    expect(erro).not.toBeInstanceOf(ErroRespostaInvalida);
    expect((erro as ErroApi).status).toBe(500);
  });

  it("falha de rede vira ErroApi com status 0", async () => {
    simularFetch(() => {
      throw new TypeError("Failed to fetch");
    });
    const erro = await requisitar("/itens", { esquema: esquemaItem }).catch((e: unknown) => e);
    expect(erro).toBeInstanceOf(ErroApi);
    expect((erro as ErroApi).status).toBe(0);
  });
});

describe("requisitar: 401 e handler global", () => {
  it("401 notifica o handler uma única vez e lança ErroApi(401)", async () => {
    simularFetch(() => respostaJson({ detail: "Não autenticado." }, 401));
    const handler = vi.fn();
    definirAoNaoAutenticado(handler);
    const erro = await requisitar("/itens", { esquema: esquemaItem }).catch((e: unknown) => e);
    expect((erro as ErroApi).status).toBe(401);
    expect((erro as ErroApi).detalhe).toBe("Não autenticado.");
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it("notificar401 true também notifica", async () => {
    simularFetch(() => respostaJson({ detail: "x" }, 401));
    const handler = vi.fn();
    definirAoNaoAutenticado(handler);
    await requisitar("/itens", { esquema: esquemaItem, notificar401: true }).catch(() => {});
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it("notificar401 false não chama o handler", async () => {
    simularFetch(() => respostaJson({ detail: "x" }, 401));
    const handler = vi.fn();
    definirAoNaoAutenticado(handler);
    const erro = await requisitar("/itens", { esquema: esquemaItem, notificar401: false }).catch(
      (e: unknown) => e,
    );
    expect((erro as ErroApi).status).toBe(401);
    expect(handler).not.toHaveBeenCalled();
  });

  it("403, 500 e sucesso não chamam o handler", async () => {
    const handler = vi.fn();
    definirAoNaoAutenticado(handler);
    for (const status of [403, 500]) {
      simularFetch(() => respostaJson({ detail: "x" }, status));
      await requisitar("/itens", { esquema: esquemaItem }).catch(() => {});
    }
    simularFetch(() => respostaJson({ id: 1, nome: "a" }));
    await requisitar("/itens", { esquema: esquemaItem });
    expect(handler).not.toHaveBeenCalled();
  });

  it("handler nulo é aceito e o erro 401 continua sendo lançado", async () => {
    simularFetch(() => respostaJson({ detail: "x" }, 401));
    definirAoNaoAutenticado(vi.fn());
    definirAoNaoAutenticado(null);
    await expect(requisitar("/itens", { esquema: esquemaItem })).rejects.toMatchObject({
      status: 401,
    });
  });

  it("novo handler substitui o anterior", async () => {
    simularFetch(() => respostaJson({ detail: "x" }, 401));
    const antigo = vi.fn();
    const novo = vi.fn();
    definirAoNaoAutenticado(antigo);
    definirAoNaoAutenticado(novo);
    await requisitar("/itens", { esquema: esquemaItem }).catch(() => {});
    expect(antigo).not.toHaveBeenCalled();
    expect(novo).toHaveBeenCalledTimes(1);
  });
});
