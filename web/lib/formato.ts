/** Formatação PT-BR. Arredonda na exibição para não vazar lixo de ponto flutuante (critério 10). */

const MOEDA = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const PCT = new Intl.NumberFormat("pt-BR", {
  style: "percent",
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

export function moeda(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return MOEDA.format(v);
}

/** `fracao` é 0..1 (ex.: 0.42 → "42,0%"). */
export function porcentagem(fracao: number | null | undefined): string {
  if (fracao === null || fracao === undefined || Number.isNaN(fracao)) return "—";
  return PCT.format(fracao);
}

export function data(d: string | Date | null | undefined): string {
  if (!d) return "—";
  const dt = typeof d === "string" ? new Date(d + "T00:00:00") : d;
  if (Number.isNaN(dt.getTime())) return "—";
  return dt.toLocaleDateString("pt-BR");
}
