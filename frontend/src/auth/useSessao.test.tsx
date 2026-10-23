import { act, renderHook, waitFor } from "@testing-library/react";
import { ErroApi, ErroRespostaInvalida } from "@/api/erros";
import { useSessao } from "@/auth/useSessao";
import { respostaJson, simularFetch, usuarioExemplo } from "@/testes/auxiliares";
import { criarClienteTeste, envolver } from "@/testes/montar";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("useSessao", () => {
  it("começa carregando e depois devolve o usuário", async () => {
    simularFetch(() => respostaJson(usuarioExemplo));
    const { result } = renderHook(() => useSessao(), { wrapper: envolver(criarClienteTeste()) });
    expect(result.current.carregando).toBe(true);
    expect(result.current.usuario).toBeUndefined();
    await waitFor(() => expect(result.current.carregando).toBe(false));
    expect(result.current.usuario).toEqual(usuarioExemplo);
    expect(result.current.erro).toBeNull();
  });

  it("401 resulta em usuario null sem erro", async () => {
    simularFetch(() => respostaJson({ detail: "Não autenticado." }, 401));
    const { result } = renderHook(() => useSessao(), { wrapper: envolver(criarClienteTeste()) });
    await waitFor(() => expect(result.current.carregando).toBe(false));
    expect(result.current.usuario).toBeNull();
    expect(result.current.erro).toBeNull();
  });

  it("erro 500 preenche erro e não vira usuario null", async () => {
    simularFetch(() => respostaJson({ detail: "Falha." }, 500));
    const { result } = renderHook(() => useSessao(), { wrapper: envolver(criarClienteTeste()) });
    await waitFor(() => expect(result.current.erro).not.toBeNull());
    expect(result.current.erro).toBeInstanceOf(ErroApi);
    expect(result.current.erro?.status).toBe(500);
    expect(result.current.usuario ?? undefined).toBeUndefined();
    expect(result.current.carregando).toBe(false);
  });

  it("falha de rede preenche erro com status 0", async () => {
    simularFetch(() => {
      throw new TypeError("Failed to fetch");
    });
    const { result } = renderHook(() => useSessao(), { wrapper: envolver(criarClienteTeste()) });
    await waitFor(() => expect(result.current.erro).not.toBeNull());
    expect(result.current.erro?.status).toBe(0);
  });

  it("resposta fora do esquema preenche erro ErroRespostaInvalida", async () => {
    simularFetch(() => respostaJson({ qualquer: "coisa" }));
    const { result } = renderHook(() => useSessao(), { wrapper: envolver(criarClienteTeste()) });
    await waitFor(() => expect(result.current.erro).not.toBeNull());
    expect(result.current.erro).toBeInstanceOf(ErroRespostaInvalida);
  });

  it("não repete a requisição ao falhar (sem retry)", async () => {
    const api = simularFetch(() => respostaJson({ detail: "Falha." }, 500));
    const { result } = renderHook(() => useSessao(), { wrapper: envolver(criarClienteTeste()) });
    await waitFor(() => expect(result.current.erro).not.toBeNull());
    expect(api.contar("GET", "/api/v1/auth/eu")).toBe(1);
  });

  it("tentarDeNovo refaz a consulta e limpa o erro", async () => {
    let falhar = true;
    const api = simularFetch(() =>
      falhar ? respostaJson({ detail: "Falha." }, 500) : respostaJson(usuarioExemplo),
    );
    const { result } = renderHook(() => useSessao(), { wrapper: envolver(criarClienteTeste()) });
    await waitFor(() => expect(result.current.erro).not.toBeNull());
    falhar = false;
    await act(async () => {
      result.current.tentarDeNovo();
    });
    await waitFor(() => expect(result.current.usuario).toEqual(usuarioExemplo));
    expect(result.current.erro).toBeNull();
    expect(api.contar("GET", "/api/v1/auth/eu")).toBe(2);
  });

  it("usa a chave ['sessao'] e reaproveita o cache entre montagens", async () => {
    const api = simularFetch(() => respostaJson(usuarioExemplo));
    const cliente = criarClienteTeste();
    const primeiro = renderHook(() => useSessao(), { wrapper: envolver(cliente) });
    await waitFor(() => expect(primeiro.result.current.usuario).toEqual(usuarioExemplo));
    expect(cliente.getQueryData(["sessao"])).toEqual(usuarioExemplo);

    const segundo = renderHook(() => useSessao(), { wrapper: envolver(cliente) });
    expect(segundo.result.current.usuario).toEqual(usuarioExemplo);
    expect(segundo.result.current.carregando).toBe(false);
    expect(api.contar("GET", "/api/v1/auth/eu")).toBe(1);
  });

  it("reflete a sessão marcada como null no cache", async () => {
    simularFetch(() => respostaJson(usuarioExemplo));
    const cliente = criarClienteTeste();
    const { result } = renderHook(() => useSessao(), { wrapper: envolver(cliente) });
    await waitFor(() => expect(result.current.usuario).toEqual(usuarioExemplo));
    act(() => {
      cliente.setQueryData(["sessao"], null);
    });
    await waitFor(() => expect(result.current.usuario).toBeNull());
  });
});
