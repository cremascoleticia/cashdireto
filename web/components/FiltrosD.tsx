"use client";

/** Filtros do Bloco D: escopo + data + status + ordenação. Dirigem a URL. */
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useTransition } from "react";
import type { EscopoTipo } from "@/lib/blocoD";

interface Props {
  escopoTipo: EscopoTipo;
  escopoValor: string | null;
  dataReferencia: string;
  status: string;
  ordem: string;
  datas: string[];
  estabelecimentos: string[];
  raizes: string[];
  grupos: string[];
}

const sel =
  "border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-teal-600";

export default function FiltrosD(p: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const sp = useSearchParams();
  const [pendente, startTransition] = useTransition();

  function set(mut: (q: URLSearchParams) => void) {
    const q = new URLSearchParams(sp.toString());
    mut(q);
    startTransition(() => router.push(`${pathname}?${q.toString()}`));
  }

  const valores =
    p.escopoTipo === "estabelecimento" ? p.estabelecimentos : p.escopoTipo === "raiz" ? p.raizes : p.grupos;

  return (
    <div className={`flex flex-wrap items-end gap-3 ${pendente ? "opacity-60" : ""}`}>
      <Campo r="Escopo">
        <select className={sel} value={p.escopoTipo} onChange={(e) => set((q) => { q.set("escopo", e.target.value); q.delete("valor"); })}>
          <option value="grupo">Grupo econômico</option>
          <option value="raiz">Raiz de CNPJ</option>
          <option value="estabelecimento">Estabelecimento</option>
        </select>
      </Campo>
      <Campo r="Valor">
        <select className={sel} value={p.escopoValor ?? ""} onChange={(e) => set((q) => { if (e.target.value) q.set("valor", e.target.value); else q.delete("valor"); })}>
          <option value="">Todos</option>
          {valores.map((v) => <option key={v} value={v}>{v}</option>)}
        </select>
      </Campo>
      <Campo r="Data">
        <select className={sel} value={p.dataReferencia} onChange={(e) => set((q) => q.set("data", e.target.value))}>
          {p.datas.map((d) => <option key={d} value={d}>{d}</option>)}
        </select>
      </Campo>
      <Campo r="Status">
        <select className={sel} value={p.status} onChange={(e) => set((q) => q.set("status", e.target.value))}>
          <option value="todos">Todos</option>
          <option value="ativo">Ativo</option>
          <option value="orfao">Órfão</option>
          <option value="pontual">Pontual</option>
        </select>
      </Campo>
      <Campo r="Ordenar por">
        <select className={sel} value={p.ordem} onChange={(e) => set((q) => q.set("ordem", e.target.value))}>
          <option value="registrado">Valor registrado</option>
          <option value="captura">Valor que trava</option>
          <option value="aproveitamento">Aproveitamento</option>
        </select>
      </Campo>
    </div>
  );
}

function Campo({ r, children }: { r: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs font-medium text-slate-500">{r}</span>
      {children}
    </label>
  );
}
