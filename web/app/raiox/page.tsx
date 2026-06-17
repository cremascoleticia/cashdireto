/**
 * Bloco B — Raio-X de colateral (foto do dia). Server Component sobre core.ur_efeitos.
 * KPIs (grupo/filial), C-B1/C-B2, G-B1 (travado por beneficiário), G-B2 (fila), risco, inventário,
 * tabela por gravame e por filial. Colunas que dependem de contrato (AP013) ficam indisponíveis.
 */
import Link from "next/link";
import FiltrosB from "@/components/FiltrosB";
import { GraficoComparacao, GraficoDistribuicao, GraficoFila, GraficoTravadoBenef } from "@/components/GraficosB";
import { getBlocoB, type EscopoTipo } from "@/lib/blocoB";
import { getOpcoesFiltro } from "@/lib/blocoC";
import { data as fmtData, moeda, porcentagem } from "@/lib/formato";

export const dynamic = "force-dynamic";

type SP = { escopo?: string; valor?: string; data?: string };

export default async function RaioXPage({ searchParams }: { searchParams: SP }) {
  const opcoes = await getOpcoesFiltro();
  if (!opcoes.datas.length) {
    return (
      <Wrapper>
        <p className="text-slate-600">Nenhum dado carregado em ur_efeitos ainda.</p>
      </Wrapper>
    );
  }

  const escopoTipo = (["estabelecimento", "raiz", "grupo"].includes(searchParams.escopo ?? "")
    ? searchParams.escopo
    : "grupo") as EscopoTipo;
  const filtros = {
    escopoTipo,
    escopoValor: searchParams.valor || null,
    dataReferencia: searchParams.data ?? opcoes.datas[0],
  };
  const r = await getBlocoB(filtros);
  const { kpis: k, callouts: c, inventario: inv } = r;
  const filaMaisFunda = r.filaPorData.reduce((m, d) => Math.max(m, d.profundidadeMax), 0);

  return (
    <Wrapper>
      <FiltrosB
        escopoTipo={filtros.escopoTipo}
        escopoValor={filtros.escopoValor}
        dataReferencia={filtros.dataReferencia}
        datas={opcoes.datas}
        estabelecimentos={opcoes.estabelecimentos}
        raizes={opcoes.raizes}
        grupos={opcoes.grupos}
      />

      {/* KPIs */}
      <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {r.escopo === "grupo" ? (
          <>
            <Kpi t="Total registrado em gravames" v={moeda(k.totalRegistrado)} />
            <Kpi t="Agenda travada (de fato)" v={moeda(k.agendaTravada)} destaque />
            <Kpi t="% que de fato trava" v={porcentagem(k.pctQueTrava)} />
            <Kpi t="Agenda total" v={moeda(k.agendaTotal)} />
            <Kpi t="Agenda livre" v={`${moeda(k.agendaLivre)} (${porcentagem(k.pctAgendaLivre)})`} />
            <Kpi t="% da agenda travada" v={porcentagem(k.pctAgendaTravada)} />
            <Kpi t="1º da fila trava (% do fluxo)" v={porcentagem(k.primeiroDaFilaTravaPct)} />
            <Kpi t="URs com saldo" v={String(inv.ursComSaldo)} />
          </>
        ) : (
          <>
            <Kpi t="Agenda da filial" v={moeda(k.agendaTotal)} />
            <Kpi t="Travado" v={moeda(k.agendaTravada)} destaque />
            <Kpi t="Livre" v={moeda(k.agendaLivre)} />
            <Kpi t="% travada" v={porcentagem(k.pctAgendaTravada)} />
            <Kpi t="Gravames na filial" v={String(inv.gravamesRegistrados)} />
            <Kpi t="Fila mais funda (credores)" v={String(filaMaisFunda)} />
          </>
        )}
      </section>

      {/* Comparação C-B1/C-B2 + G-B1 */}
      <div className="grid lg:grid-cols-2 gap-4">
        <Card titulo={r.escopo === "grupo" ? "Registrado × travado de fato (C-B1)" : "Agenda × travado × livre (C-B2)"}>
          <GraficoComparacao dados={r.comparacao} />
        </Card>
        <Card titulo="Valor que trava por beneficiário (G-B1)">
          <GraficoTravadoBenef dados={r.travadoPorBeneficiario} />
          {r.meuCnpj && <p className="text-xs text-slate-400 mt-1">Em vermelho: meu CNPJ ({r.meuCnpj}).</p>}
        </Card>
      </div>

      {/* G-B2 */}
      <Card titulo="Profundidade da fila por data de liquidação (G-B2)">
        <GraficoFila dados={r.filaPorData} />
      </Card>

      {/* Risco */}
      <section className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <Callout
          titulo="Concentração na registradora"
          v={c.concentracaoRegistradora ? `${porcentagem(c.concentracaoRegistradora.pct)} — ${c.concentracaoRegistradora.registradora}` : "—"}
        />
        <Callout titulo="Gravames órfãos (travam 0)" v={String(c.gravamesOrfaos)} alerta={c.gravamesOrfaos > 0} />
        <Callout titulo="1º da fila trava" v={porcentagem(k.primeiroDaFilaTravaPct)} />
        <Callout titulo="URs de fila rasa (≤2 credores)" v={String(c.ursFilaRasa)} />
        <Callout
          titulo="…dessas, desprotegidas (sem saldo)"
          v={String(c.ursFilaRasaDesprotegidas)}
          alerta={c.ursFilaRasaDesprotegidas > 0}
        />
        <Callout
          titulo="URs de fila profunda (prio > 2)"
          v={String(c.ursFilaProfunda)}
          alerta={c.ursFilaProfunda > 0}
        />
        <Callout titulo="Horizonte da agenda" v={`${fmtData(c.horizonteInicio)} → ${fmtData(c.horizonteFim)}`} />
      </section>

      {/* Inventário */}
      <Card titulo="Inventário (escopo)">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-x-6 gap-y-2 text-sm">
          <Item k="Filiais" v={inv.filiais} />
          <Item k="Gravames registrados" v={inv.gravamesRegistrados} />
          <Item k="Trava fixa" v={inv.travaFixo} />
          <Item k="Trava percentual" v={inv.travaPercentual} />
          <Item k="Gravames sobre o grupo todo" v={inv.gravamesGrupoTodo} />
          <Item k="Gravames sobre 1 filial" v={inv.gravamesUmaFilial} />
          <Item k="Bandeiras / arranjos" v={inv.bandeiras} />
          <Item k="Beneficiários distintos" v={inv.beneficiariosDistintos} />
          <Item k="URs com saldo" v={inv.ursComSaldo} />
        </div>
      </Card>

      {/* Distribuição por posição na fila */}
      <Card titulo="Distribuição de gravames por posição na fila">
        <GraficoDistribuicao dados={r.distribuicaoPosicao} rotuloX="posição na fila" />
      </Card>

      {/* A tabela-mestre de gravames/contratos é o Bloco D */}
      <div className="rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">
        A tabela completa de gravames/contratos (com vigência, abrangência, aproveitamento e status
        Ativo/Órfão/Pontual) fica no{" "}
        <Link className="text-teal-700 underline" href="/contratos">
          Bloco D — Contratos / Gravames
        </Link>
        .
      </div>

      {/* Tabela por filial */}
      <Card titulo={`Por filial (${r.porFilial.length})`} semPad>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-100 text-left text-slate-600">
              <tr>
                <th className="p-2">Estabelecimento</th>
                <th className="p-2 text-right">Agenda</th>
                <th className="p-2 text-right">Travado</th>
                <th className="p-2 text-right">Livre</th>
                <th className="p-2 text-right">Nº gravames</th>
                <th className="p-2 text-right">1º da fila</th>
                <th className="p-2 text-right">% comprometimento</th>
              </tr>
            </thead>
            <tbody>
              {r.porFilial.slice(0, 300).map((f) => (
                <tr key={f.estabelecimento} className="border-t border-slate-100">
                  <td className="p-2 font-mono text-xs">{f.estabelecimento}</td>
                  <td className="p-2 text-right">{moeda(f.agenda)}</td>
                  <td className="p-2 text-right">{moeda(f.travado)}</td>
                  <td className="p-2 text-right">{moeda(f.livre)}</td>
                  <td className="p-2 text-right">{f.nGravames}</td>
                  <td className="p-2 text-right">{f.primeiroDaFila ?? "—"}</td>
                  <td className="p-2 text-right">{porcentagem(f.pctComprometimento)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </Wrapper>
  );
}

function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <main className="max-w-7xl mx-auto p-6 flex flex-col gap-5">
      <h1 className="text-2xl font-semibold text-slate-800">Raio-X de colateral</h1>
      {children}
    </main>
  );
}

function Kpi({ t, v, destaque }: { t: string; v: string; destaque?: boolean }) {
  return (
    <div className={`rounded-xl p-4 shadow ${destaque ? "bg-teal-700 text-white" : "bg-white"}`}>
      <div className={`text-xs ${destaque ? "text-teal-100" : "text-slate-500"}`}>{t}</div>
      <div className="text-lg font-semibold mt-1">{v}</div>
    </div>
  );
}

function Callout({ titulo, v, alerta }: { titulo: string; v: string; alerta?: boolean }) {
  return (
    <div className={`rounded-xl p-3 shadow ${alerta ? "bg-red-50 border border-red-200" : "bg-white"}`}>
      <div className="text-xs text-slate-500">{titulo}</div>
      <div className={`text-sm font-semibold mt-1 ${alerta ? "text-red-700" : "text-slate-800"}`}>{v}</div>
    </div>
  );
}

function Card({ titulo, children, semPad }: { titulo: string; children: React.ReactNode; semPad?: boolean }) {
  return (
    <section className="bg-white rounded-xl shadow overflow-hidden">
      <h2 className="text-sm font-semibold text-slate-700 p-4 pb-2">{titulo}</h2>
      <div className={semPad ? "" : "p-4 pt-2"}>{children}</div>
    </section>
  );
}

function Item({ k, v }: { k: string; v: number }) {
  return (
    <div className="flex justify-between border-b border-slate-100 py-1">
      <span className="text-slate-500">{k}</span>
      <span className="font-medium">{v}</span>
    </div>
  );
}
