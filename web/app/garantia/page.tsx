/**
 * Bloco C — Gestão de garantia (núcleo do portal). Server Component: lê o banco, roda a cascata
 * e renderiza KPIs + G-C1 + tabela por UR. Filtros dirigem a URL (recalcula sem full reload).
 */
import Filtros from "@/components/Filtros";
import GraficoCC1 from "@/components/GraficoCC1";
import { beneficiarioPadrao, getBlocoC, getOpcoesFiltro, type EscopoTipo, type FiltrosC } from "@/lib/blocoC";
import type { StatusEfeito } from "@/lib/cascata";
import { data as fmtData, moeda, porcentagem } from "@/lib/formato";

export const dynamic = "force-dynamic";

type SP = { benef?: string; escopo?: string; valor?: string; data?: string };

export default async function GarantiaPage({ searchParams }: { searchParams: SP }) {
  const opcoes = await getOpcoesFiltro();

  if (!opcoes.beneficiarios.length) {
    return (
      <Wrapper>
        <p className="text-slate-600">
          Nenhum efeito carregado ainda. Suba arquivos AP005 para popular <code>ur_efeitos</code>.
        </p>
      </Wrapper>
    );
  }

  const escopoTipo = (["estabelecimento", "raiz", "grupo"].includes(searchParams.escopo ?? "")
    ? searchParams.escopo
    : "grupo") as EscopoTipo;
  const dataReferencia = searchParams.data ?? opcoes.datas[0];
  const filtros: FiltrosC = {
    beneficiario:
      searchParams.benef ?? (await beneficiarioPadrao(dataReferencia)) ?? opcoes.beneficiarios[0].cnpj,
    escopoTipo,
    escopoValor: searchParams.valor || null,
    dataReferencia,
  };

  const { kpis, grafico, tabela } = await getBlocoC(filtros);

  return (
    <Wrapper>
      <Filtros
        opcoes={opcoes}
        beneficiario={filtros.beneficiario}
        escopoTipo={filtros.escopoTipo}
        escopoValor={filtros.escopoValor}
        dataReferencia={filtros.dataReferencia}
      />

      <section className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-3">
        <Kpi titulo="Efeito constituído (meu)" valor={moeda(kpis.efeitoConstituido)} />
        <Kpi titulo="Valor onerado total (contexto)" valor={moeda(kpis.oneradoTotalContexto)} />
        <Kpi titulo="A pagar por prioridade (meu)" valor={moeda(kpis.aPagar)} destaque />
        <Kpi titulo="Aproveitamento" valor={porcentagem(kpis.aproveitamento)} />
        <Kpi
          titulo="Perda por subordinação"
          valor={moeda(kpis.perdaPorSubordinacao)}
          alerta={kpis.perdaPorSubordinacao > 0}
        />
      </section>

      {kpis.ursSemSaldo > 0 && (
        <p className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
          {kpis.ursSemSaldo} UR(s) sem saldo disponível informado — excluídas do “a pagar” (não estimadas).
        </p>
      )}

      <section className="bg-white rounded-xl shadow p-4">
        <h2 className="text-sm font-semibold text-slate-700 mb-3">
          Constituído × A pagar por data de liquidação
          <span className="font-normal text-slate-400"> — o gap = perda por subordinação</span>
        </h2>
        <GraficoCC1 dados={grafico} />
      </section>

      <section className="bg-white rounded-xl shadow overflow-hidden">
        <h2 className="text-sm font-semibold text-slate-700 p-4 pb-2">
          URs onde sou beneficiário ({tabela.length})
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-100 text-left text-slate-600">
              <tr>
                <th className="p-2">UR</th>
                <th className="p-2">Estabelecimento</th>
                <th className="p-2">Titular da UR</th>
                <th className="p-2">Bandeira</th>
                <th className="p-2">Data de liquidação</th>
                <th className="p-2 text-right">Posição na fila</th>
                <th className="p-2">Regra</th>
                <th className="p-2 text-right">Valor registrado (meu)</th>
                <th className="p-2 text-right">Onerado total da UR</th>
                <th className="p-2 text-right">A pagar / trava (meu)</th>
                <th className="p-2 text-center">Credor &gt; 2ª?</th>
                <th className="p-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {tabela.slice(0, 500).map((r) => (
                <tr key={r.ur_id} className="border-t border-slate-100">
                  <td className="p-2 font-mono text-xs">{r.ur_id.slice(0, 8)}</td>
                  <td className="p-2 font-mono text-xs">{r.estabelecimento}</td>
                  <td className="p-2 font-mono text-xs">{r.titular ?? "—"}</td>
                  <td className="p-2 text-xs">{r.arranjo ?? "—"}</td>
                  <td className="p-2">{fmtData(r.dataLiquidacao)}</td>
                  <td className="p-2 text-right">{r.minhaPosicao ?? "—"}</td>
                  <td className="p-2 text-xs">{r.regra ?? "—"}</td>
                  <td className="p-2 text-right">{moeda(r.constituidoMeu)}</td>
                  <td className="p-2 text-right">{moeda(r.oneradoTotalUR)}</td>
                  <td className="p-2 text-right">{moeda(r.aPagarMeu)}</td>
                  <td className="p-2 text-center">{r.credorAlem2a ? "sim" : "—"}</td>
                  <td className="p-2">
                    <Badge status={r.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {tabela.length > 500 && (
            <p className="p-3 text-xs text-slate-500">
              Mostrando 500 de {tabela.length} URs.
            </p>
          )}
        </div>
      </section>
    </Wrapper>
  );
}

function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <main className="max-w-7xl mx-auto p-6 flex flex-col gap-5">
      <h1 className="text-2xl font-semibold text-slate-800">Gestão de garantia</h1>
      {children}
    </main>
  );
}

function Kpi({
  titulo,
  valor,
  destaque,
  alerta,
}: {
  titulo: string;
  valor: string;
  destaque?: boolean;
  alerta?: boolean;
}) {
  return (
    <div
      className={`rounded-xl p-4 shadow ${
        destaque ? "bg-teal-700 text-white" : alerta ? "bg-red-50 border border-red-200" : "bg-white"
      }`}
    >
      <div className={`text-xs ${destaque ? "text-teal-100" : "text-slate-500"}`}>{titulo}</div>
      <div className={`text-lg font-semibold mt-1 ${alerta ? "text-red-700" : ""}`}>{valor}</div>
    </div>
  );
}

const CORES: Record<StatusEfeito, string> = {
  Integral: "bg-emerald-100 text-emerald-800",
  Parcial: "bg-amber-100 text-amber-800",
  Subordinado: "bg-red-100 text-red-800",
  "Sem saldo": "bg-sky-100 text-sky-700",
  "Sem saldo informado": "bg-slate-100 text-slate-600",
};

function Badge({ status }: { status: StatusEfeito }) {
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${CORES[status]}`}>{status}</span>
  );
}
