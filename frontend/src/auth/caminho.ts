const PROIBIDOS = /[\\\u0000-\u001f\u007f]/;

// Aceita só caminho interno; barras duplicadas, invertidas e esquemas viram redirecionamento externo.
export function caminhoSeguro(valor: string | null | undefined, padrao = "/"): string {
  if (!valor || !valor.startsWith("/") || valor.startsWith("//")) return padrao;
  if (PROIBIDOS.test(valor) || valor.includes("://")) return padrao;
  return valor;
}
