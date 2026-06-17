"use client";

/**
 * G-C1 — Constituído × A pagar por data de liquidação (barras agrupadas).
 * O gap entre as barras = perda por subordinação (o que o gravame nominal esconde).
 */
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { PontoGraficoC } from "@/lib/blocoC";
import { moeda } from "@/lib/formato";

const fmt = new Intl.NumberFormat("pt-BR", {
  notation: "compact",
  style: "currency",
  currency: "BRL",
});

export default function GraficoCC1({ dados }: { dados: PontoGraficoC[] }) {
  if (!dados.length) {
    return <p className="text-sm text-slate-500">Sem dados para o filtro atual.</p>;
  }
  return (
    <ResponsiveContainer width="100%" height={320}>
      <BarChart data={dados} margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="data" tick={{ fontSize: 11 }} />
        <YAxis tickFormatter={(v: number) => fmt.format(v)} tick={{ fontSize: 11 }} width={70} />
        <Tooltip
          formatter={(
            v: number | string | ReadonlyArray<number | string> | undefined,
            nome: string | number | undefined,
          ): [string, string] => {
            const n = Array.isArray(v) ? Number(v[0]) : Number(v);
            return [moeda(n), String(nome)];
          }}
        />
        <Legend />
        <Bar dataKey="constituido" name="Constituído (meu)" fill="#94a3b8" />
        <Bar dataKey="aPagar" name="A pagar por prioridade" fill="#0f766e" />
      </BarChart>
    </ResponsiveContainer>
  );
}
