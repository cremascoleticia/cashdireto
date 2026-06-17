/**
 * Bloco A — Cockpit de monitoramento. Esqueleto honesto: a estrutura toda existe, mas os
 * indicadores que dependem de dado operacional (ainda ausente) aparecem como "indisponível"
 * com a fonte que falta — nunca tela muda (regra 9). O painel de ingestão (P-A2) é real.
 */
import { GRAFICOS_COCKPIT, getOperacoes, getStatusIngestao, KPIS_COCKPIT } from "@/lib/blocoA";
import { data as fmtData } from "@/lib/formato";

export const dynamic = "force-dynamic";

export default async function CockpitPage() {
  const [operacoes, ingestao] = await Promise.all([getOperacoes(), getStatusIngestao()]);

  return (
    <main className="max-w-7xl mx-auto p-6 flex flex-col gap-5">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-2xl font-semibold text-slate-800">Cockpit de monitoramento</h1>
        <label className="flex items-center gap-2 text-sm">
          <span className="text-slate-500">Operação:</span>
          <select className="border border-slate-300 rounded-lg px-3 py-2 bg-white" disabled={!operacoes.length}>
            {operacoes.length ? (
              operacoes.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.cedente_grupo}
                </option>
              ))
            ) : (
              <option>Nenhuma operação cadastrada</option>
            )}
          </select>
        </label>
      </div>

      <div className="rounded-lg border border-amber-300 bg-amber-50 text-amber-800 px-4 py-3 text-sm">
        <b>Aguardando dados operacionais.</b> O cockpit (Razão de Garantia, faturamento, repasse,
        diluição) precisa das tabelas <code>operacao</code>, <code>parcela</code>,{" "}
        <code>faturamento_diario</code>, <code>repasse_diario</code> e do extrato do domicílio — ainda
        vazias. Os indicadores abaixo ficam <b>indisponíveis</b> (não estimados) até o dado chegar.
      </div>

      {/* KPIs (indisponíveis) */}
      <section className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {KPIS_COCKPIT.map((k) => (
          <div key={k.chave} className="rounded-xl bg-white shadow p-4">
            <div className="text-xs text-slate-500">{k.titulo}</div>
            <div className="text-lg font-semibold mt-1 text-slate-300">indisponível</div>
            <div className="text-[11px] text-slate-400 mt-1">requer: {k.depende}</div>
          </div>
        ))}
      </section>

      {/* Gráficos (indisponíveis) */}
      <section className="grid lg:grid-cols-3 gap-4">
        {GRAFICOS_COCKPIT.map((g) => (
          <div key={g.titulo} className="bg-white rounded-xl shadow p-4">
            <h2 className="text-sm font-semibold text-slate-700">{g.titulo}</h2>
            <div className="h-40 flex items-center justify-center text-slate-300 text-sm border border-dashed border-slate-200 rounded-lg mt-3">
              indisponível
            </div>
            <div className="text-[11px] text-slate-400 mt-2">requer: {g.depende}</div>
          </div>
        ))}
      </section>

      <section className="grid lg:grid-cols-2 gap-4">
        {/* P-A1 — exceções/alertas */}
        <div className="bg-white rounded-xl shadow p-4">
          <h2 className="text-sm font-semibold text-slate-700 mb-2">P-A1 · Exceções e alertas</h2>
          <p className="text-sm text-slate-500">
            Sem alertas calculáveis ainda — as regras (RG &lt; mínimo, faturamento abaixo do baseline,
            repasse &lt; esperado, gravame órfão ativo) dependem dos dados operacionais. Quando
            chegarem, dado ausente vira alerta aqui (nunca silêncio).
          </p>
        </div>

        {/* P-A2 — status de ingestão (REAL) */}
        <div className="bg-white rounded-xl shadow overflow-hidden">
          <h2 className="text-sm font-semibold text-slate-700 p-4 pb-2">P-A2 · Status de ingestão</h2>
          <table className="w-full text-sm">
            <thead className="bg-slate-100 text-left text-slate-600">
              <tr>
                <th className="p-2">Fonte</th>
                <th className="p-2">Última foto</th>
                <th className="p-2">Status</th>
                <th className="p-2 text-right">Arquivos</th>
              </tr>
            </thead>
            <tbody>
              {ingestao.length ? (
                ingestao.map((i) => (
                  <tr key={i.tipo} className="border-t border-slate-100">
                    <td className="p-2 font-medium">{i.tipo}</td>
                    <td className="p-2">{fmtData(i.ultimaData)}</td>
                    <td className="p-2">
                      <span className="px-2 py-0.5 rounded-full text-xs bg-emerald-100 text-emerald-800">
                        {i.status ?? "—"}
                      </span>
                    </td>
                    <td className="p-2 text-right">{i.nArquivos}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td className="p-3 text-slate-500" colSpan={4}>
                    Nenhuma fonte ingerida.
                  </td>
                </tr>
              )}
              {/* fontes esperadas que NÃO chegaram = evidência negativa */}
              {["faturamento_diario", "repasse_diario", "extrato_domicilio"].map((esperada) => (
                <tr key={esperada} className="border-t border-slate-100">
                  <td className="p-2 font-medium text-slate-500">{esperada}</td>
                  <td className="p-2">—</td>
                  <td className="p-2">
                    <span className="px-2 py-0.5 rounded-full text-xs bg-red-100 text-red-800">ausente</span>
                  </td>
                  <td className="p-2 text-right">0</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
