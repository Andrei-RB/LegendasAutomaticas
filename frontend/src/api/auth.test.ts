import { entrar, obterSessao, sair } from "@/api/auth";
import { definirAoNaoAutenticado } from "@/api/cliente";
import { ErroApi, ErroRespostaInvalida } from "@/api/erros";
import { respostaJson, simularFetch, usuarioExemplo } from "@/testes/auxiliares";

afterEach(() => {
  definirAoNaoAutenticado(null);
  vi.unstubAllGlobals();
});

describe("entrar", () => {
  it("faz POST /auth/login com e-mail e senha e devolve o usuário", async () => {
    const api = simularFetch(() => respostaJson(usuarioExemplo));
    const usuario = await entrar({ email: "usuario@exemplo.test", senha: "segredo-123" });
    expect(usuario).toEqual(usuarioExemplo);
    expect(api.requisicoes[0]).toMatchObject({
      metodo: "POST",
      caminho: "/api/v1/auth/login",
      corpo: { email: "usuario@exemplo.test", senha: "segredo-123" },
    });
  });

  it("401 lança ErroApi com detail e não notifica o handler global", async () => {
    simularFetch(() => respostaJson({ detail: "E-mail ou senha incorretos." }, 401));
    const handler = vi.fn();
    definirAoNaoAutenticado(handler);
    const erro = await entrar({ email: "usuario@exemplo.test", senha: "x" }).catch(
      (e: unknown) => e,
    );
    expect(erro).toBeInstanceOf(ErroApi);
    expect((erro as ErroApi).status).toBe(401);
    expect((erro as ErroApi).detalhe).toBe("E-mail ou senha incorretos.");
    expect(handler).not.toHaveBeenCalled();
  });

  it("usuário fora do esquema lança ErroRespostaInvalida", async () => {
    simularFetch(() => respostaJson({ id: "nao-uuid" }));
    await expect(entrar({ email: "usuario@exemplo.test", senha: "x" })).rejects.toBeInstanceOf(
      ErroRespostaInvalida,
    );
  });
});

describe("sair", () => {
  it("faz POST /auth/logout e resolve com 204", async () => {
    const api = simularFetch(() => respostaJson(undefined, 204));
    await expect(sair()).resolves.toBeUndefined();
    expect(api.requisicoes[0]).toMatchObject({ metodo: "POST", caminho: "/api/v1/auth/logout" });
  });
});

describe("obterSessao", () => {
  it("faz GET /auth/eu e devolve o usuário", async () => {
    const api = simularFetch(() => respostaJson(usuarioExemplo));
    await expect(obterSessao()).resolves.toEqual(usuarioExemplo);
    expect(api.requisicoes[0]).toMatchObject({ metodo: "GET", caminho: "/api/v1/auth/eu" });
  });

  it("401 lança ErroApi sem notificar o handler global", async () => {
    simularFetch(() => respostaJson({ detail: "Não autenticado." }, 401));
    const handler = vi.fn();
    definirAoNaoAutenticado(handler);
    await expect(obterSessao()).rejects.toMatchObject({ status: 401 });
    expect(handler).not.toHaveBeenCalled();
  });
});
