/**
 * Bloco D — Contratos / Gravames. Tabela-mestre dos gravames (agrupados por contrato_id), com
 * totais, derivados (aproveitamento, abrangência, status), G-D1 e distribuições. Server Component.
 */
import FiltrosD from "@/components/FiltrosD";
import { GraficoDistribuicao, GraficoGD1 } from "@/components/GraficosB";
import { getBlocoD, type EscopoTipo, type FiltrosD as TFiltrosD } from "@/lib/blocoD";
import { getOpcoesFiltro } from "@/lib/blocoC";
import { data as fmtData, moeda, porcentagem } from "@/lib/formato";

export const dynamic = "force-dynamic";

type SP = { escopo?: string; valor?: string; data?: string; status?: string; ordem?: string };

export default async function ContratosPage({ searchParams }: { searchParams: SP }) {
  const opcoes = await getOpcoesFiltro();
  if (!opcoes.datas.length) {
    return (
      <main className="max-w-7xl mx-auto p-6">
        <h1 className="text-2xl font-semibold text-slate-800">Contratos / Gravames</h1>
        <p className="text-slate-600 mt-2">Nenhum dado carregado.</p>
      </main>
    );
  }

  const escopoTipo = (["estabelecimento", "raiz", "grupo"].includes(searchParams.escopo ?? "")
    ? searchParams.escopo
    : "grupo") as EscopoTipo;
  const status = (["todos", "ativo", "orfao", "pontual"].includes(searchParams.status ?? "")
    ? searchParams.status
    : "todos") as TFiltrosD["status"];
  const ordem = (["registrado", "captura", "aproveitamento"].includes(searchParams.ordem ?? "")
    ? searchParams.ordem
    : "registrado") as TFiltrosD["ordem"];
  const filtros: TFiltrosD = {
    escopoTipo,
    escopoValor: searchParams.valor || null,
    dataReferencia: searchParams.data ?? opcoes.datas[0],
    status,
    ordem,
  };

  const r = await getBlocoD(filtros);

  return (
    <main className="max-w-7xl mx-auto p-6 flex flex-col gap-5">
      <h1 className="text-2xl font-semibold text-slate-800">Contratos / Gravames</h1>

      <FiltrosD
        escopoTipo={filtros.escopoTipo}
        escopoValor={filtros.escopoValor}
        dataReferencia={filtros.dataReferencia}
        status={filtros.status}
        ordem={filtros.ordem}
        datas={opcoes.datas}
        estabelecimentos={opcoes.estabelecimentos}
        raizes={opcoes.raizes}
        grupos={opcoes.grupos}
      />

      <section className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <Kpi t="Total registrado" v={moeda(r.totalRegistrado)} />
        <Kpi t="Total que trava" v={moeda(r.totalCaptura)} destaque />
        <Kpi t="Aproveitamento global" v={porcentagem(r.aproveitamentoGlobal)} />
        <Kpi t="Gravames" v={`${r.nGravames} (${r.nComCaptura} c/ captura)`} />
        <Kpi t="Órfãos (travam 0)" v={String(r.nOrfaos)} alerta={r.nOrfaos > 0} />
      </section>

      <div className="grid lg:grid-cols-2 gap-4">
        <Card t="G-D1 · Registrado × travado por gravame (top 12)">
          <GraficoGD1 dados={r.topGD1} />
        </Card>
        <div className="flex flex-col gap-4">
          <Card t="Por tipo de trava">
            <GraficoDistribuicao dados={r.distTipoTrava.map((d) => ({ posicao: d.rotulo, n: d.n }))} />
          </Card>
          <Card t="Por posição na fila">
            <GraficoDistribuicao dados={r.distPosicao} rotuloX="posição" />
          </Card>
        </div>
      </div>

      <section className="bg-white rounded-xl shadow overflow-hidden">
        <h2 className="text-sm font-semibold text-slate-700 p-4 pb-2">Gravames ({r.linhas.length})</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-100 text-left text-slate-600">
              <tr>
                <th className="p-2">Contrato</th>
                <th className="p-2">Regra</th>
                <th className="p-2">Tipo pag.</th>
                <th className="p-2">Credor</th>
                <th className="p-2 text-right">Prio mín</th>
                <th className="p-2 text-right">Nº CNPJ</th>
                <th className="p-2 text-right">Nº Arr.</th>
                <th className="p-2 text-right">Cobert. datas</th>
                <th className="p-2 text-right">Registrado</th>
                <th className="p-2 text-right">Que trava</th>
                <th className="p-2 text-right">Aproveit.</th>
                <th className="p-2 text-right">% fluxo</th>
                <th className="p-2">Abrangência</th>
                <th className="p-2">Status</th>
                <th className="p-2">Vigência</th>
              </tr>
            </thead>
            <tbody>
              {r.linhas.slice(0, 500).map((l) => (
                <tr key={l.contrato} className="border-t border-slate-100">
                  <td className="p-2 font-mono text-xs">{l.contrato.slice(0, 10)}</td>
                  <td className="p-2 text-xs">{l.regra ?? "—"}</td>
                  <td className="p-2 text-xs">{l.tipoPagamento ?? "—"}</td>
                  <td className="p-2 font-mono text-xs">{l.beneficiario ?? "—"}</td>
                  <td className="p-2 text-right">{l.prioMin ?? "—"}</td>
                  <td className="p-2 text-right">{l.nCnpj}</td>
                  <td className="p-2 text-right">{l.nArr}</td>
                  <td className="p-2 text-right">{l.cobertDatasPct === null ? "—" : `${l.cobertDatasPct.toFixed(1)}%`}</td>
                  <td className="p-2 text-right">{moeda(l.registrado)}</td>
                  <td className="p-2 text-right">{moeda(l.captura)}</td>
                  <td className="p-2 text-right">{porcentagem(l.aproveitamento)}</td>
                  <td className="p-2 text-right">{porcentagem(l.pctFluxo)}</td>
                  <td className="p-2 text-xs">{l.abrangencia}</td>
                  <td className="p-2"><BadgeD status={l.status} /></td>
                  <td className="p-2 text-xs">{fmtData(l.inicio)} – {fmtData(l.fim)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}

function Kpi({ t, v, destaque, alerta }: { t: string; v: string; destaque?: boolean; alerta?: boolean }) {
  return (
    <div className={`rounded-xl p-4 shadow ${destaque ? "bg-teal-700 text-white" : alerta ? "bg-red-50 border border-red-200" : "bg-white"}`}>
      <div className={`text-xs ${destaque ? "text-teal-100" : "text-slate-500"}`}>{t}</div>
      <div className={`text-base font-semibold mt-1 ${alerta ? "text-red-700" : ""}`}>{v}</div>
    </div>
  );
}

function Card({ t, children }: { t: string; children: React.ReactNode }) {
  return (
    <section className="bg-white rounded-xl shadow p-4">
      <h2 className="text-sm font-semibold text-slate-700 mb-3">{t}</h2>
      {children}
    </section>
  );
}

const CORES_D: Record<string, string> = {
  Ativo: "bg-emerald-100 text-emerald-800",
  "Órfão": "bg-red-100 text-red-800",
  Pontual: "bg-amber-100 text-amber-800",
};
function BadgeD({ status }: { status: string }) {
  return <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${CORES_D[status] ?? "bg-slate-100"}`}>{status}</span>;
}
