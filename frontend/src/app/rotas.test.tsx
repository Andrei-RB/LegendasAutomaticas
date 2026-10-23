import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { z } from "zod";
import { definirAoNaoAutenticado, requisitar } from "@/api/cliente";
import { Provedores, criarClienteConsulta } from "@/app/provedores";
import { rotas } from "@/app/rotas";
import { useTema } from "@/tema/armazem";
import {
  respostaJson,
  simularFetch,
  usuarioExemplo,
  type RequisicaoSimulada,
} from "@/testes/auxiliares";
import { montarRotas } from "@/testes/montar";

const EU = "/api/v1/auth/eu";
const LOGIN = "/api/v1/auth/login";
const LOGOUT = "/api/v1/auth/logout";

interface EstadoApi {
  logado: boolean;
  respostaLogin?: (req: RequisicaoSimulada) => Response;
  respostaLogout?: (req: RequisicaoSimulada) => Response;
}

// Simula o backend de autenticação com sessão mutável.
function simularApi(estado: EstadoApi) {
  return simularFetch((req) => {
    if (req.caminho === EU && req.metodo === "GET") {
      return estado.logado
        ? respostaJson(usuarioExemplo)
        : respostaJson({ detail: "Não autenticado." }, 401);
    }
    if (req.caminho === LOGIN && req.metodo === "POST") {
      if (estado.respostaLogin) return estado.respostaLogin(req);
      estado.logado = true;
      return respostaJson(usuarioExemplo);
    }
    if (req.caminho === LOGOUT && req.metodo === "POST") {
      if (estado.respostaLogout) return estado.respostaLogout(req);
      estado.logado = false;
      return respostaJson(undefined, 204);
    }
    if (req.caminho === "/api/v1/qualquer") {
      return respostaJson({ detail: "Sessão expirada." }, 401);
    }
    return respostaJson({ detail: "Rota inesperada." }, 404);
  });
}

function montarApp(inicial: string) {
  const cliente = criarClienteConsulta();
  const montagem = montarRotas(rotas, inicial, cliente);
  return montagem;
}

async function preencherEEntrar(email: string, senha: string) {
  const usuario = userEvent.setup();
  await usuario.type(await screen.findByLabelText("E-mail"), email);
  await usuario.type(screen.getByLabelText("Senha"), senha);
  await usuario.click(screen.getByRole("button", { name: "Entrar" }));
}

beforeEach(() => {
  useTema.getState().definirTema("escuro");
});

afterEach(() => {
  definirAoNaoAutenticado(null);
  vi.unstubAllGlobals();
});

describe("exportações de app", () => {
  it("rotas é uma lista e Provedores/criarClienteConsulta existem", () => {
    expect(Array.isArray(rotas)).toBe(true);
    expect(typeof Provedores).toBe("function");
    expect(criarClienteConsulta()).toHaveProperty("getQueryData");
  });
});

describe("login e proteção de rotas", () => {
  it("/painel sem sessão mostra a tela de login e guarda o destino", async () => {
    simularApi({ logado: false });
    const { router } = montarApp("/painel");
    expect(await screen.findByRole("button", { name: "Entrar" })).toBeInTheDocument();
    expect(screen.getByLabelText("E-mail")).toBeInTheDocument();
    expect(screen.getByLabelText("Senha")).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/entrar");
    expect(router.state.location.search).toBe("?de=%2Fpainel");
  });

  it("login com sucesso envia credenciais normalizadas e volta ao destino", async () => {
    const api = simularApi({ logado: false });
    const { router } = montarApp("/painel");
    await preencherEEntrar("  Usuario@Exemplo.TEST ", "segredo-123");
    await waitFor(() => expect(router.state.location.pathname).toBe("/painel"));
    const envio = api.requisicoes.find((r) => r.caminho === LOGIN);
    expect(envio?.corpo).toEqual({ email: "usuario@exemplo.test", senha: "segredo-123" });
    expect(await screen.findByRole("link", { name: "Painel" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Entrar" })).not.toBeInTheDocument();
  });

  it.each([
    ["URL absoluta", "https%3A%2F%2Fx.test"],
    ["protocolo relativo", "%2F%2Fx.test"],
    ["esquema javascript", "javascript%3Aalert(1)"],
  ])("destino inseguro (%s) é ignorado após o login", async (_nome, de) => {
    simularApi({ logado: false });
    const { router } = montarApp(`/entrar?de=${de}`);
    await preencherEEntrar("usuario@exemplo.test", "segredo-123");
    await waitFor(() => expect(router.state.location.pathname).toBe("/"));
    expect(router.state.location.search).toBe("");
  });

  it("login com 401 mostra o detail da API e permanece no login", async () => {
    const api = simularApi({
      logado: false,
      respostaLogin: () => respostaJson({ detail: "E-mail ou senha incorretos." }, 401),
    });
    const { router } = montarApp("/entrar");
    await preencherEEntrar("usuario@exemplo.test", "errada");
    const alerta = await screen.findByRole("alert");
    expect(alerta).toHaveTextContent("E-mail ou senha incorretos.");
    expect(router.state.location.pathname).toBe("/entrar");
    expect(api.contar("POST", LOGIN)).toBe(1);
  });

  it("formulário vazio mostra as mensagens de validação sem chamar o login", async () => {
    const api = simularApi({ logado: false });
    montarApp("/entrar");
    await userEvent.click(await screen.findByRole("button", { name: "Entrar" }));
    expect(await screen.findByText("Informe um e-mail válido.")).toBeInTheDocument();
    expect(screen.getByText("Informe a senha.")).toBeInTheDocument();
    expect(api.contar("POST", LOGIN)).toBe(0);
  });

  it("e-mail inválido com senha preenchida mostra só a mensagem de e-mail", async () => {
    const api = simularApi({ logado: false });
    montarApp("/entrar");
    await preencherEEntrar("sem-arroba", "segredo-123");
    expect(await screen.findByText("Informe um e-mail válido.")).toBeInTheDocument();
    expect(screen.queryByText("Informe a senha.")).not.toBeInTheDocument();
    expect(api.contar("POST", LOGIN)).toBe(0);
  });

  it("401 em requisição protegida depois de logado leva ao login", async () => {
    simularApi({ logado: true });
    const { router, cliente } = montarApp("/painel");
    expect(await screen.findByRole("link", { name: "Painel" })).toBeInTheDocument();

    await act(async () => {
      await requisitar("/qualquer", { esquema: z.unknown() }).catch(() => {});
    });

    await waitFor(() => expect(router.state.location.pathname).toBe("/entrar"));
    expect(router.state.location.search).toBe("?de=%2Fpainel");
    expect(cliente.getQueryData(["sessao"])).toBeNull();
    expect(await screen.findByRole("button", { name: "Entrar" })).toBeInTheDocument();
  });

  it("logout faz POST e volta ao login", async () => {
    const api = simularApi({ logado: true });
    const { router } = montarApp("/painel");
    await userEvent.click(await screen.findByRole("button", { name: "Sair" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/entrar"));
    expect(api.contar("POST", LOGOUT)).toBe(1);
    expect(await screen.findByRole("button", { name: "Entrar" })).toBeInTheDocument();
    expect(router.state.location.search).toBe("");
  });

  it("falha de rede no logout mantém a sessão e mostra o erro", async () => {
    simularApi({
      logado: true,
      respostaLogout: () => {
        throw new TypeError("falha de rede");
      },
    });
    const { router } = montarApp("/painel");
    await userEvent.click(await screen.findByRole("button", { name: "Sair" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Sem conexão com o servidor. Verifique a rede e tente de novo.",
    );
    expect(router.state.location.pathname).toBe("/painel");
  });

  it("503 no logout (revogação falhou, cookie apagado) volta ao login", async () => {
    simularApi({ logado: true, respostaLogout: () => respostaJson({ detail: "x" }, 503) });
    const { router } = montarApp("/painel");
    await userEvent.click(await screen.findByRole("button", { name: "Sair" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/entrar"));
  });

  it("erros de validação são anunciados e o foco vai ao primeiro campo inválido", async () => {
    simularApi({ logado: false });
    montarApp("/entrar");
    await userEvent.click(await screen.findByRole("button", { name: "Entrar" }));
    const alertas = await screen.findAllByRole("alert");
    expect(alertas).toHaveLength(2);
    expect(screen.getByLabelText("E-mail")).toHaveFocus();
  });
});

describe("layout e navegação", () => {
  it("menu tem Biblioteca, Painel e Configurações e navega entre as rotas", async () => {
    simularApi({ logado: true });
    const { router } = montarApp("/");
    const usuario = userEvent.setup();

    expect(await screen.findByRole("link", { name: "Biblioteca" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Painel" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Configurações" })).toBeInTheDocument();

    await usuario.click(screen.getByRole("link", { name: "Painel" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/painel"));

    await usuario.click(screen.getByRole("link", { name: "Configurações" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/config"));

    await usuario.click(screen.getByRole("link", { name: "Biblioteca" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/"));
  });

  it("rota inexistente autenticada mostra 'Página não encontrada'", async () => {
    simularApi({ logado: true });
    montarApp("/nao-existe");
    expect(await screen.findByText(/Página não encontrada/)).toBeInTheDocument();
  });
});

describe("alternador de tema", () => {
  it("no layout alterna a classe dark", async () => {
    simularApi({ logado: true });
    montarApp("/painel");
    const botao = await screen.findByRole("button", { name: "Alternar tema" });
    expect(document.documentElement).toHaveClass("dark");
    await userEvent.click(botao);
    expect(document.documentElement).not.toHaveClass("dark");
    await userEvent.click(screen.getByRole("button", { name: "Alternar tema" }));
    expect(document.documentElement).toHaveClass("dark");
  });

  it("na tela de login alterna a classe dark", async () => {
    simularApi({ logado: false });
    montarApp("/entrar");
    const botao = await screen.findByRole("button", { name: "Alternar tema" });
    expect(document.documentElement).toHaveClass("dark");
    await userEvent.click(botao);
    expect(document.documentElement).not.toHaveClass("dark");
  });
});
