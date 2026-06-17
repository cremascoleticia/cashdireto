"use client";

/**
 * Filtros do Bloco C: beneficiário + escopo do cedente (estabelecimento/raiz/grupo) + data.
 * Dirigem a URL (searchParams); a página é Server Component e re-renderiza por navegação soft
 * (sem full reload). Trocar qualquer filtro recalcula KPIs/gráfico/tabela.
 */
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useTransition } from "react";
import type { EscopoTipo, OpcoesFiltro } from "@/lib/blocoC";

interface Props {
  opcoes: OpcoesFiltro;
  beneficiario: string;
  escopoTipo: EscopoTipo;
  escopoValor: string | null;
  dataReferencia: string;
}

export default function Filtros(p: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const sp = useSearchParams();
  const [pendente, startTransition] = useTransition();

  function atualizar(mut: (params: URLSearchParams) => void) {
    const params = new URLSearchParams(sp.toString());
    mut(params);
    startTransition(() => router.push(`${pathname}?${params.toString()}`));
  }

  const valoresEscopo =
    p.escopoTipo === "estabelecimento"
      ? p.opcoes.estabelecimentos
      : p.escopoTipo === "raiz"
        ? p.opcoes.raizes
        : p.opcoes.grupos;

  return (
    <div className={`flex flex-wrap items-end gap-4 ${pendente ? "opacity-60" : ""}`}>
      <Campo rotulo="Beneficiário (meu CNPJ)">
        <select
          className={sel}
          value={p.beneficiario}
          onChange={(e) => atualizar((q) => q.set("benef", e.target.value))}
        >
          {p.opcoes.beneficiarios.map((b) => (
            <option key={b.cnpj} value={b.cnpj}>
              {b.cnpj}
            </option>
          ))}
        </select>
      </Campo>

      <Campo rotulo="Escopo do cedente">
        <select
          className={sel}
          value={p.escopoTipo}
          onChange={(e) =>
            atualizar((q) => {
              q.set("escopo", e.target.value);
              q.delete("valor"); // troca de tipo → volta para "todos"
            })
          }
        >
          <option value="grupo">Grupo econômico</option>
          <option value="raiz">Raiz de CNPJ</option>
          <option value="estabelecimento">Estabelecimento</option>
        </select>
      </Campo>

      <Campo rotulo="&nbsp;">
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
          <option value="">Todos</option>
          {valoresEscopo.map((v) => (
            <option key={v} value={v}>
              {v}
            </option>
          ))}
        </select>
      </Campo>

      <Campo rotulo="Data de referência">
        <select
          className={sel}
          value={p.dataReferencia}
          onChange={(e) => atualizar((q) => q.set("data", e.target.value))}
        >
          {p.opcoes.datas.map((d) => (
            <option key={d} value={d}>
              {d}
            </option>
          ))}
        </select>
      </Campo>
    </div>
  );
}

const sel =
  "border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white min-w-[12rem] focus:outline-none focus:ring-2 focus:ring-teal-600";

function Campo({ rotulo, children }: { rotulo: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1">
      <span
        className="text-xs font-medium text-slate-500"
        dangerouslySetInnerHTML={{ __html: rotulo }}
      />
      {children}
    </label>
  );
}
