"use client";

/** Filtros do Bloco B: escopo do cedente (grupo/raiz/estabelecimento) + data. Dirigem a URL. */
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useTransition } from "react";
import type { EscopoTipo } from "@/lib/blocoB";

interface Props {
  escopoTipo: EscopoTipo;
  escopoValor: string | null;
  dataReferencia: string;
  datas: string[];
  estabelecimentos: string[];
  raizes: string[];
  grupos: string[];
}

const sel =
  "border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white min-w-[12rem] focus:outline-none focus:ring-2 focus:ring-teal-600";

export default function FiltrosB(p: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const sp = useSearchParams();
  const [pendente, startTransition] = useTransition();

  function atualizar(mut: (q: URLSearchParams) => void) {
    const q = new URLSearchParams(sp.toString());
    mut(q);
    startTransition(() => router.push(`${pathname}?${q.toString()}`));
  }

  const valores =
    p.escopoTipo === "estabelecimento" ? p.estabelecimentos : p.escopoTipo === "raiz" ? p.raizes : p.grupos;

  return (
    <div className={`flex flex-wrap items-end gap-4 ${pendente ? "opacity-60" : ""}`}>
      <label className="flex flex-col gap-1">
        <span className="text-xs font-medium text-slate-500">Escopo do cedente</span>
        <select
          className={sel}
          value={p.escopoTipo}
          onChange={(e) =>
            atualizar((q) => {
              q.set("escopo", e.target.value);
              q.delete("valor");
            })
          }
        >
          <option value="grupo">Grupo econômico</option>
          <option value="raiz">Raiz de CNPJ</option>
          <option value="estabelecimento">Estabelecimento</option>
        </select>
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-xs font-medium text-slate-500">Valor</span>
        <select
          className={sel}
          value={p.escopoValor ?? ""}
          onChange={(e) =>
            atualizar((q) => {
              if (e.target.value) q.set("valor", e.target.value);
              else q.delete("valor");
            })
          }
        >
          <option value="">Todos (agregado do grupo)</option>
          {valores.map((v) => (
            <option key={v} value={v}>
              {v}
            </option>
          ))}
        </select>
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-xs font-medium text-slate-500">Data de referência</span>
        <select className={sel} value={p.dataReferencia} onChange={(e) => atualizar((q) => q.set("data", e.target.value))}>
          {p.datas.map((d) => (
            <option key={d} value={d}>
              {d}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}
