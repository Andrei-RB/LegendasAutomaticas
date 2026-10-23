export const catalogo = {
  marca: "Viraliza+",
  menu: {
    navegacao: "Navegação principal",
    biblioteca: "Biblioteca",
    painel: "Painel",
    config: "Configurações",
  },
  acoes: {
    sair: "Sair",
    alternarTema: "Alternar tema",
    tentarDeNovo: "Tentar de novo",
    voltarInicio: "Voltar para o início",
  },
  tema: {
    escuro: "Tema escuro",
    claro: "Tema claro",
  },
  entrar: {
    titulo: "Entrar",
    descricao: "Acesse sua conta para continuar.",
    email: "E-mail",
    senha: "Senha",
    enviar: "Entrar",
    enviando: "Entrando…",
    credenciais_invalidas: "E-mail ou senha incorretos.",
  },
  validacao: {
    email_invalido: "Informe um e-mail válido.",
    senha_obrigatoria: "Informe a senha.",
  },
  erros: {
    rede: "Sem conexão com o servidor. Verifique a rede e tente de novo.",
    ocupado: "O servidor está ocupado. Tente novamente em instantes.",
    generico: "Algo deu errado. Tente novamente.",
  },
  sessao: {
    carregando: "Carregando…",
    erro: "Não foi possível verificar a sessão.",
  },
  paginas: {
    biblioteca: {
      titulo: "Biblioteca",
      vazio: "Nenhum vídeo por aqui ainda.",
    },
    painel: {
      titulo: "Painel",
      descricao: "Cotas de IA e saúde do sistema aparecerão aqui.",
    },
    config: {
      titulo: "Configurações",
      descricao: "Chaves, limites e preferências aparecerão aqui.",
    },
    nao_encontrada: {
      titulo: "Página não encontrada",
      descricao: "O endereço não existe ou foi movido.",
    },
  },
} as const;

export type Catalogo = typeof catalogo;
