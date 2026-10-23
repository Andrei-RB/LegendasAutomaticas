import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useEffect, useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router";
import { entrar } from "@/api/auth";
import { ErroApi } from "@/api/erros";
import { esquemaLogin } from "@/api/esquemas";
import { chaveErro } from "@/api/mensagemErro";
import { caminhoSeguro } from "@/auth/caminho";
import { CHAVE_SESSAO } from "@/auth/useSessao";
import { AlternarTema } from "@/componentes/AlternarTema";
import { Botao } from "@/componentes/ui/botao";
import { Campo } from "@/componentes/ui/campo";
import { Cartao } from "@/componentes/ui/cartao";
import { Rotulo } from "@/componentes/ui/rotulo";

type ChaveValidacao = "validacao.email_invalido" | "validacao.senha_obrigatoria";
interface ErrosCampo {
  email?: ChaveValidacao;
  senha?: ChaveValidacao;
}

function chaveValidacao(mensagem: string): ChaveValidacao | undefined {
  if (mensagem === "validacao.email_invalido" || mensagem === "validacao.senha_obrigatoria") {
    return mensagem;
  }
  return undefined;
}

export function Entrar() {
  const { t } = useTranslation();
  const navegar = useNavigate();
  const [parametros] = useSearchParams();
  const cliente = useQueryClient();
  const idEmail = useId();
  const idSenha = useId();
  const [email, definirEmail] = useState("");
  const [senha, definirSenha] = useState("");
  const [erros, definirErros] = useState<ErrosCampo>({});

  // Na tela de login não há sessão conhecida; limpar aqui evita corrida com a guarda no logout.
  useEffect(() => cliente.removeQueries(), [cliente]);

  const login = useMutation({
    mutationFn: entrar,
    onSuccess: (usuario) => {
      cliente.setQueryData(CHAVE_SESSAO, usuario);
      void navegar(caminhoSeguro(parametros.get("de")), { replace: true });
    },
  });

  function aoEnviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    const lido = esquemaLogin.safeParse({ email, senha });
    if (!lido.success) {
      const novos: ErrosCampo = {};
      for (const problema of lido.error.issues) {
        const campo = problema.path[0];
        const chave = chaveValidacao(problema.message);
        if (chave && (campo === "email" || campo === "senha") && !novos[campo]) {
          novos[campo] = chave;
        }
      }
      definirErros(novos);
      return;
    }
    definirErros({});
    login.mutate(lido.data);
  }

  const erroLogin = login.error;
  let mensagemLogin: string | null = null;
  if (erroLogin instanceof ErroApi && erroLogin.status === 401) {
    mensagemLogin = t("entrar.credenciais_invalidas");
  } else if (erroLogin) {
    mensagemLogin = t(chaveErro(erroLogin));
  }

  return (
    <main className="relative grid min-h-dvh place-items-center p-4">
      <div className="absolute top-3 right-3">
        <AlternarTema />
      </div>
      <Cartao className="w-full max-w-sm">
        <h1 className="text-2xl font-semibold tracking-tight">{t("entrar.titulo")}</h1>
        <p className="mt-1 text-sm text-muted-foreground">{t("entrar.descricao")}</p>
        <form noValidate onSubmit={aoEnviar} className="mt-6 flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Rotulo htmlFor={idEmail}>{t("entrar.email")}</Rotulo>
            <Campo
              id={idEmail}
              type="email"
              autoComplete="username"
              value={email}
              onChange={(e) => definirEmail(e.target.value)}
              aria-invalid={erros.email ? true : undefined}
              aria-describedby={erros.email ? `${idEmail}-erro` : undefined}
            />
            {erros.email && (
              <p id={`${idEmail}-erro`} className="text-sm text-destructive">
                {t(erros.email)}
              </p>
            )}
          </div>
          <div className="flex flex-col gap-1.5">
            <Rotulo htmlFor={idSenha}>{t("entrar.senha")}</Rotulo>
            <Campo
              id={idSenha}
              type="password"
              autoComplete="current-password"
              value={senha}
              onChange={(e) => definirSenha(e.target.value)}
              aria-invalid={erros.senha ? true : undefined}
              aria-describedby={erros.senha ? `${idSenha}-erro` : undefined}
            />
            {erros.senha && (
              <p id={`${idSenha}-erro`} className="text-sm text-destructive">
                {t(erros.senha)}
              </p>
            )}
          </div>
          {mensagemLogin && (
            <p role="alert" className="text-sm text-destructive">
              {mensagemLogin}
            </p>
          )}
          <Botao type="submit" disabled={login.isPending}>
            {login.isPending ? t("entrar.enviando") : t("entrar.enviar")}
          </Botao>
        </form>
      </Cartao>
    </main>
  );
}
