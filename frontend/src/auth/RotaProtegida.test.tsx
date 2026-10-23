import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useLocation, type RouteObject } from "react-router";
import { RotaProtegida } from "@/auth/RotaProtegida";
import { respostaJson, simularFetch, usuarioExemplo } from "@/testes/auxiliares";
import { montarRotas } from "@/testes/montar";

function Entrada() {
  const local = useLocation();
  return <p data-testid="entrada">{`login${local.search}`}</p>;
}

const rotas: RouteObject[] = [
  {
    element: <RotaProtegida />,
    children: [{ path: "/painel", element: <p>Conteúdo protegido</p> }],
  },
  { path: "/entrar", element: <Entrada /> },
];

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("RotaProtegida", () => {
  it("renderiza a rota filha quando há sessão", async () => {
    simularFetch(() => respostaJson(usuarioExemplo));
    montarRotas(rotas, "/painel");
    expect(await screen.findByText("Conteúdo protegido")).toBeInTheDocument();
  });

  it("mostra role status enquanto a sessão carrega", async () => {
    let liberar: (r: Response) => void = () => {};
    simularFetch(() => new Promise<Response>((resolver) => (liberar = resolver)));
    montarRotas(rotas, "/painel");
    expect(await screen.findByRole("status")).toBeInTheDocument();
    expect(screen.queryByText("Conteúdo protegido")).not.toBeInTheDocument();
    liberar(respostaJson(usuarioExemplo));
    expect(await screen.findByText("Conteúdo protegido")).toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("sem sessão (401) redireciona com replace para /entrar?de=", async () => {
    simularFetch(() => respostaJson({ detail: "Não autenticado." }, 401));
    const { router } = montarRotas(rotas, "/painel?a=1");
    await waitFor(() => expect(router.state.location.pathname).toBe("/entrar"));
    expect(router.state.location.search).toBe(`?de=${encodeURIComponent("/painel?a=1")}`);
    expect(router.state.historyAction).toBe("REPLACE");
    expect(screen.queryByText("Conteúdo protegido")).not.toBeInTheDocument();
  });

  it("erro não-401 mostra alerta com 'Tentar de novo' e não redireciona", async () => {
    simularFetch(() => respostaJson({ detail: "Falha." }, 500));
    const { router } = montarRotas(rotas, "/painel");
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Tentar de novo" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/painel");
    expect(screen.queryByText("Conteúdo protegido")).not.toBeInTheDocument();
  });

  it("falha de rede também mostra alerta sem redirecionar", async () => {
    simularFetch(() => {
      throw new TypeError("Failed to fetch");
    });
    const { router } = montarRotas(rotas, "/painel");
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/painel");
  });

  it("'Tentar de novo' refaz a consulta e exibe o conteúdo", async () => {
    let falhar = true;
    const api = simularFetch(() =>
      falhar ? respostaJson({ detail: "Falha." }, 500) : respostaJson(usuarioExemplo),
    );
    montarRotas(rotas, "/painel");
    const botao = await screen.findByRole("button", { name: "Tentar de novo" });
    falhar = false;
    await userEvent.click(botao);
    expect(await screen.findByText("Conteúdo protegido")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(api.contar("GET", "/api/v1/auth/eu")).toBe(2);
  });
});
