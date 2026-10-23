import { esquemaLogin, esquemaUsuario } from "@/api/esquemas";
import { usuarioExemplo } from "@/testes/auxiliares";

function mensagens(resultado: { error?: { issues: { message: string }[] } }) {
  return resultado.error?.issues.map((i) => i.message) ?? [];
}

describe("esquemaUsuario", () => {
  it("aceita usuário completo", () => {
    expect(esquemaUsuario.parse(usuarioExemplo)).toEqual(usuarioExemplo);
  });

  it.each([
    ["id não uuid", { ...usuarioExemplo, id: "123" }],
    ["sem e-mail", { ...usuarioExemplo, email: undefined }],
    ["sem nome_usuario", { ...usuarioExemplo, nome_usuario: undefined }],
    ["sem idioma", { ...usuarioExemplo, idioma: undefined }],
    ["id numérico", { ...usuarioExemplo, id: 7 }],
  ])("rejeita %s", (_nome, entrada) => {
    expect(esquemaUsuario.safeParse(entrada).success).toBe(false);
  });
});

describe("esquemaLogin", () => {
  it("normaliza e-mail com trim e minúsculas", () => {
    const dados = esquemaLogin.parse({ email: "  Usuario@Exemplo.TEST ", senha: "segredo" });
    expect(dados.email).toBe("usuario@exemplo.test");
    expect(dados.senha).toBe("segredo");
  });

  it.each(["", "   ", "semarroba", "a@", "@exemplo.test", "a b@exemplo.test"])(
    "e-mail %j devolve validacao.email_invalido",
    (email) => {
      const r = esquemaLogin.safeParse({ email, senha: "segredo" });
      expect(r.success).toBe(false);
      expect(mensagens(r)).toEqual(["validacao.email_invalido"]);
    },
  );

  it("senha vazia devolve validacao.senha_obrigatoria", () => {
    const r = esquemaLogin.safeParse({ email: "usuario@exemplo.test", senha: "" });
    expect(r.success).toBe(false);
    expect(mensagens(r)).toEqual(["validacao.senha_obrigatoria"]);
  });

  it("formulário vazio devolve as duas mensagens", () => {
    const r = esquemaLogin.safeParse({ email: "", senha: "" });
    expect(mensagens(r).sort()).toEqual([
      "validacao.email_invalido",
      "validacao.senha_obrigatoria",
    ]);
  });
});
