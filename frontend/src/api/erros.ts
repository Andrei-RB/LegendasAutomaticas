export class ErroApi extends Error {
  readonly status: number;
  readonly detalhe: unknown;

  constructor(status: number, detalhe?: unknown) {
    super(typeof detalhe === "string" ? detalhe : `Erro ${status}`);
    this.name = "ErroApi";
    this.status = status;
    this.detalhe = detalhe;
  }
}

export class ErroRespostaInvalida extends ErroApi {
  constructor() {
    super(502);
    this.name = "ErroRespostaInvalida";
  }
}
