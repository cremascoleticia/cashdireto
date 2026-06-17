"use client";

/** Gráficos do Bloco B: C-B1/C-B2 (comparação), G-B1 (travado por beneficiário), G-B2 (fila). */
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { BarraTravadoBenef } from "@/lib/blocoB";
import { moeda } from "@/lib/formato";

const compacto = new Intl.NumberFormat("pt-BR", { notation: "compact", style: "currency", currency: "BRL" });

type V = number | string | ReadonlyArray<number | string> | undefined;
const fmtMoeda = (v: V, n: string | number | undefined): [string, string] => [
  moeda(Array.isArray(v) ? Number(v[0]) : Number(v)),
  String(n),
];

export function GraficoComparacao({ dados }: { dados: { rotulo: string; valor: number }[] }) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={dados} margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="rotulo" tick={{ fontSize: 12 }} />
        <YAxis tickFormatter={(v: number) => compacto.format(v)} tick={{ fontSize: 11 }} width={70} />
        <Tooltip formatter={fmtMoeda} />
        <Bar dataKey="valor" name="Valor" fill="#0f766e" />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function GraficoTravadoBenef({ dados }: { dados: BarraTravadoBenef[] }) {
  if (!dados.length) return <p className="text-sm text-slate-500">Sem valor travado no filtro atual.</p>;
  return (
    <ResponsiveContainer width="100%" height={Math.max(220, dados.length * 26)}>
      <BarChart data={dados} layout="vertical" margin={{ top: 8, right: 24, left: 8, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" horizontal={false} />
        <XAxis type="number" tickFormatter={(v: number) => compacto.format(v)} tick={{ fontSize: 11 }} />
        <YAxis type="category" dataKey="beneficiario" width={130} tick={{ fontSize: 10 }} />
        <Tooltip formatter={fmtMoeda} />
        <Bar dataKey="travado" name="Valor que trava">
          {dados.map((d) => (
            <Cell key={d.beneficiario} fill={d.meu ? "#b91c1c" : "#0f766e"} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

export function GraficoFila({
  dados,
}: {
  dados: { data: string; registrado: number; profundidadeMax: number }[];
}) {
  if (!dados.length) return <p className="text-sm text-slate-500">Sem agenda no filtro atual.</p>;
  return (
    <ResponsiveContainer width="100%" height={300}>
      <ComposedChart data={dados} margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="data" tick={{ fontSize: 10 }} />
        <YAxis
          yAxisId="esq"
          tickFormatter={(v: number) => compacto.format(v)}
          tick={{ fontSize: 11 }}
          width={70}
        />
        <YAxis yAxisId="dir" orientation="right" allowDecimals={false} tick={{ fontSize: 11 }} width={40} />
        <Tooltip />
        <Legend />
        <Bar yAxisId="esq" dataKey="registrado" name="Valor registrado" fill="#94a3b8" />
        <Line
          yAxisId="dir"
          type="monotone"
          dataKey="profundidadeMax"
          name="Credores na fila (máx)"
          stroke="#b91c1c"
          strokeWidth={2}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
