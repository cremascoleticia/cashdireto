/**
 * Bloco B — Raio-X de colateral (foto do dia). Visão do CEDENTE: quanto da agenda está registrado
 * em gravames vs quanto de fato trava, agenda livre, fila por prioridade, concentração e horizonte.
 *
 * Tudo deriva de `core.ur_efeitos` (AP005). Itens que dependem de contrato (AP013 — vigência,
 * filiais cobertas, % de dias cobertos) ficam marcados indisponível (sem dado real; regra 9).
 */
import { consultar } from "./db";
import { aPagarUR, type Efeito, type UR } from "./cascata";

export type EscopoTipo = "estabelecimento" | "raiz" | "grupo";

export interface FiltrosB {
  escopoTipo: EscopoTipo;
  escopoValor: string | null; // null = todos (agregado do grupo todo)
  dataReferencia: string;
}

const COLUNA_ESCOPO: Record<EscopoTipo, string> = {
  estabelecimento: "estabelecimento_cnpj",
  raiz: "raiz_cnpj",
  grupo: "grupo_economico",
};

function num(v: unknown): number | null {
  if (v === null || v === undefined) return null;
  const n = typeof v === "number" ? v : Number(v);
  return Number.isNaN(n) ? null : n;
}

interface URComMeta extends UR {
  estabelecimento: string;
  arranjo: string | null;
  registradora: string | null;
  dataLiquidacao: string | null;
  efeitosMeta: { beneficiario: string | null; arranjo: string | null; regra: string | null }[];
}

interface LinhaB {
  ur_id: string;
  estabelecimento_cnpj: string;
  arranjo: string | null;
  registradora: string | null;
  data_liquidacao: string | null;
  valor_ur: unknown;
  prioridade: number | null;
  beneficiario_cnpj: string | null;
  regra: string | null;
  valor_constituido: unknown;
}

export interface KpisB {
  totalRegistrado: number; // Σ valor_constituido (nominal)
  agendaTravada: number; // Σ travado de fato (cascata)
  pctQueTrava: number | null; // travada / registrado
  agendaTotal: number; // Σ valor_ur (distinct UR)
  agendaLivre: number; // total − travada
  pctAgendaLivre: number | null;
  pctAgendaTravada: number | null; // travada / total
  primeiroDaFilaTravaPct: number | null; // a pagar ao 1º da fila / agenda total
}

export interface Callouts {
  concentracaoRegistradora: { registradora: string; pct: number } | null;
  gravamesOrfaos: number; // beneficiários com registrado>0 e travado=0
  ursFilaRasa: number; // URs com ≤2 credores distintos
  ursFilaRasaDesprotegidas: number; // dessas, com valor_ur ausente/zero
  ursComSaldo: number;
  horizonteInicio: string | null;
  horizonteFim: string | null;
}

export interface Inventario {
  filiais: number;
  gravamesRegistrados: number; // nº de efeitos
  travaFixo: number;
  travaPercentual: number;
  gravamesGrupoTodo: number; // beneficiários presentes em >1 filial
  gravamesUmaFilial: number; // beneficiários numa única filial
  bandeiras: number;
  ursComSaldo: number;
}

export interface LinhaGravame {
  beneficiario: string;
  posicaoFila: number | null;
  arranjos: string;
  valorRegistrado: number;
  valorQueTrava: number;
  pctAgendaGrupo: number | null;
}

export interface LinhaFilial {
  estabelecimento: string;
  agenda: number;
  travado: number;
  livre: number;
  nGravames: number;
  primeiroDaFila: number | null;
  pctComprometimento: number | null;
}

export interface BarraTravadoBenef {
  beneficiario: string;
  travado: number;
  meu: boolean;
}

export interface ResultadoBlocoB {
  escopo: "grupo" | "filial";
  kpis: KpisB;
  callouts: Callouts;
  inventario: Inventario;
  comparacao: { rotulo: string; valor: number }[]; // C-B1 (grupo) ou C-B2 (filial)
  travadoPorBeneficiario: BarraTravadoBenef[]; // G-B1
  filaPorData: { data: string; registrado: number; profundidadeMax: number }[]; // G-B2
  porGravame: LinhaGravame[];
  porFilial: LinhaFilial[];
  meuCnpj: string | null;
}

async function carregarURs(f: FiltrosB): Promise<URComMeta[]> {
  const params: unknown[] = [f.dataReferencia];
  let escopoPred = "";
  if (f.escopoValor) {
    params.push(f.escopoValor);
    escopoPred = `and ${COLUNA_ESCOPO[f.escopoTipo]} = $2`;
  }
  const sql = `
    select ur_id, estabelecimento_cnpj, arranjo, registradora,
           to_char(data_liquidacao,'YYYY-MM-DD') data_liquidacao,
           valor_ur, prioridade, beneficiario_cnpj, regra, valor_constituido
    from core.ur_efeitos
    where data_referencia = $1 ${escopoPred}
    order by ur_id, prioridade asc nulls last`;
  const linhas = await consultar<LinhaB>(sql, params);

  const mapa = new Map<string, URComMeta>();
  for (const l of linhas) {
    let ur = mapa.get(l.ur_id);
    if (!ur) {
      ur = {
        ur_id: l.ur_id,
        valor_ur: num(l.valor_ur),
        efeitos: [],
        estabelecimento: l.estabelecimento_cnpj,
        arranjo: l.arranjo,
        registradora: l.registradora,
        dataLiquidacao: l.data_liquidacao,
        efeitosMeta: [],
      };
      mapa.set(l.ur_id, ur);
    }
    if (l.beneficiario_cnpj !== null) {
      const efeito: Efeito = {
        prioridade: l.prioridade,
        beneficiario_cnpj: l.beneficiario_cnpj,
        valor_constituido: num(l.valor_constituido) ?? 0,
      };
      ur.efeitos.push(efeito);
      ur.efeitosMeta.push({ beneficiario: l.beneficiario_cnpj, arranjo: l.arranjo, regra: l.regra });
    }
  }
  return Array.from(mapa.values());
}

async function getMeuCnpj(): Promise<string | null> {
  const r = await consultar<{ c: string }>(
    "select distinct unnest(detentor_proprio) c from core.parametro_titular limit 1",
  );
  return r[0]?.c ?? null;
}

const semana = (d: string | null) => d ?? "sem data";

export async function getBlocoB(f: FiltrosB): Promise<ResultadoBlocoB> {
  const urs = await carregarURs(f);
  const meuCnpj = await getMeuCnpj();
  const escopo: "grupo" | "filial" = f.escopoTipo === "estabelecimento" && f.escopoValor ? "filial" : "grupo";

  let totalRegistrado = 0;
  let agendaTravada = 0;
  let agendaTotal = 0;
  let primeiroDaFilaTrava = 0;
  let ursComSaldo = 0;

  const travadoBenef = new Map<string, number>();
  const registradoBenef = new Map<string, number>();
  const arranjosBenef = new Map<string, Set<string>>();
  const posicaoBenef = new Map<string, number>();
  const filiaisBenef = new Map<string, Set<string>>();
  const porRegistradora = new Map<string, number>();
  const porFilial = new Map<string, { agenda: number; travado: number; nGravames: number; prioMin: number | null }>();
  const porData = new Map<string, { registrado: number; profundidadeMax: number }>();
  const bandeiras = new Set<string>();
  let travaFixo = 0;
  let travaPercentual = 0;
  let ursFilaRasa = 0;
  let ursFilaRasaDesprotegidas = 0;
  let horizonteInicio: string | null = null;
  let horizonteFim: string | null = null;

  for (const ur of urs) {
    const res = aPagarUR(ur);
    const registradoUR = res.oneradoTotal;
    const valorUR = ur.valor_ur ?? 0;
    const travadoUR =
      res.status === "sem_saldo_informado"
        ? 0
        : Array.from(res.aPagarPorBeneficiario.values()).reduce((a, b) => a + b, 0);

    totalRegistrado += registradoUR;
    agendaTotal += valorUR;
    agendaTravada += travadoUR;
    if (valorUR > 0) ursComSaldo += 1;

    // 1º da fila: a pagar ao efeito de menor prioridade
    if (res.status === "ok" && ur.efeitos.length) {
      const prioMin = Math.min(...ur.efeitos.filter((e) => e.prioridade !== null).map((e) => e.prioridade as number));
      const seniorBenef = ur.efeitos.find((e) => e.prioridade === prioMin)?.beneficiario_cnpj;
      if (seniorBenef) primeiroDaFilaTrava += res.aPagarPorBeneficiario.get(seniorBenef) ?? 0;
    }

    // por beneficiário
    for (const e of ur.efeitos) {
      if (!e.beneficiario_cnpj) continue;
      registradoBenef.set(e.beneficiario_cnpj, (registradoBenef.get(e.beneficiario_cnpj) ?? 0) + Math.max(0, e.valor_constituido));
      if (!arranjosBenef.has(e.beneficiario_cnpj)) arranjosBenef.set(e.beneficiario_cnpj, new Set());
      if (ur.arranjo) arranjosBenef.get(e.beneficiario_cnpj)!.add(ur.arranjo);
      if (!filiaisBenef.has(e.beneficiario_cnpj)) filiaisBenef.set(e.beneficiario_cnpj, new Set());
      filiaisBenef.get(e.beneficiario_cnpj)!.add(ur.estabelecimento);
      if (e.prioridade !== null) {
        const atual = posicaoBenef.get(e.beneficiario_cnpj);
        posicaoBenef.set(e.beneficiario_cnpj, atual === undefined ? e.prioridade : Math.min(atual, e.prioridade));
      }
    }
    for (const m of ur.efeitosMeta) {
      if (m.regra === "fixo") travaFixo += 1;
      else if (m.regra === "percentual") travaPercentual += 1;
    }
    for (const [b, v] of Array.from(res.aPagarPorBeneficiario))
      travadoBenef.set(b, (travadoBenef.get(b) ?? 0) + v);

    if (ur.registradora) porRegistradora.set(ur.registradora, (porRegistradora.get(ur.registradora) ?? 0) + registradoUR);
    if (ur.arranjo) bandeiras.add(ur.arranjo);

    // por filial
    const ff = porFilial.get(ur.estabelecimento) ?? { agenda: 0, travado: 0, nGravames: 0, prioMin: null };
    ff.agenda += valorUR;
    ff.travado += travadoUR;
    ff.nGravames += ur.efeitos.length;
    const prios = ur.efeitos.filter((e) => e.prioridade !== null).map((e) => e.prioridade as number);
    if (prios.length) ff.prioMin = ff.prioMin === null ? Math.min(...prios) : Math.min(ff.prioMin, ...prios);
    porFilial.set(ur.estabelecimento, ff);

    // fila rasa
    const credores = new Set(ur.efeitos.map((e) => e.beneficiario_cnpj).filter(Boolean));
    if (credores.size <= 2) {
      ursFilaRasa += 1;
      if (valorUR <= 0) ursFilaRasaDesprotegidas += 1;
    }

    // G-B2 por data
    const k = semana(ur.dataLiquidacao);
    const pd = porData.get(k) ?? { registrado: 0, profundidadeMax: 0 };
    pd.registrado += registradoUR;
    pd.profundidadeMax = Math.max(pd.profundidadeMax, credores.size);
    porData.set(k, pd);

    // horizonte
    if (ur.dataLiquidacao) {
      if (!horizonteInicio || ur.dataLiquidacao < horizonteInicio) horizonteInicio = ur.dataLiquidacao;
      if (!horizonteFim || ur.dataLiquidacao > horizonteFim) horizonteFim = ur.dataLiquidacao;
    }
  }

  const agendaLivre = agendaTotal - agendaTravada;
  const kpis: KpisB = {
    totalRegistrado,
    agendaTravada,
    pctQueTrava: totalRegistrado > 0 ? agendaTravada / totalRegistrado : null,
    agendaTotal,
    agendaLivre,
    pctAgendaLivre: agendaTotal > 0 ? agendaLivre / agendaTotal : null,
    pctAgendaTravada: agendaTotal > 0 ? agendaTravada / agendaTotal : null,
    primeiroDaFilaTravaPct: agendaTotal > 0 ? primeiroDaFilaTrava / agendaTotal : null,
  };

  // callouts
  let concentracaoRegistradora: Callouts["concentracaoRegistradora"] = null;
  if (totalRegistrado > 0 && porRegistradora.size) {
    const [reg, val] = Array.from(porRegistradora.entries()).sort((a, b) => b[1] - a[1])[0];
    concentracaoRegistradora = { registradora: reg, pct: val / totalRegistrado };
  }
  let gravamesOrfaos = 0;
  for (const [b, reg] of Array.from(registradoBenef)) {
    if (reg > 0 && (travadoBenef.get(b) ?? 0) <= 1e-6) gravamesOrfaos += 1;
  }

  const callouts: Callouts = {
    concentracaoRegistradora,
    gravamesOrfaos,
    ursFilaRasa,
    ursFilaRasaDesprotegidas,
    ursComSaldo,
    horizonteInicio,
    horizonteFim,
  };

  // inventário
  let gravamesGrupoTodo = 0;
  let gravamesUmaFilial = 0;
  for (const fil of Array.from(filiaisBenef.values())) {
    if (fil.size > 1) gravamesGrupoTodo += 1;
    else gravamesUmaFilial += 1;
  }
  const inventario: Inventario = {
    filiais: porFilial.size,
    gravamesRegistrados: travaFixo + travaPercentual,
    travaFixo,
    travaPercentual,
    gravamesGrupoTodo,
    gravamesUmaFilial,
    bandeiras: bandeiras.size,
    ursComSaldo,
  };

  // G-B1
  const travadoPorBeneficiario: BarraTravadoBenef[] = Array.from(travadoBenef.entries())
    .map(([beneficiario, travado]) => ({ beneficiario, travado, meu: beneficiario === meuCnpj }))
    .filter((x) => x.travado > 0)
    .sort((a, b) => b.travado - a.travado)
    .slice(0, 15);

  // C-B1 (grupo) / C-B2 (filial)
  const comparacao =
    escopo === "grupo"
      ? [
          { rotulo: "Registrado", valor: totalRegistrado },
          { rotulo: "Travado de fato", valor: agendaTravada },
        ]
      : [
          { rotulo: "Agenda total", valor: agendaTotal },
          { rotulo: "Travado", valor: agendaTravada },
          { rotulo: "Livre", valor: agendaLivre },
        ];

  // por gravame (beneficiário) — colunas AP013 (vigência/filiais cobertas/% dias) ficam fora (sem dado)
  const porGravame: LinhaGravame[] = Array.from(registradoBenef.keys())
    .map((b) => ({
      beneficiario: b,
      posicaoFila: posicaoBenef.get(b) ?? null,
      arranjos: Array.from(arranjosBenef.get(b) ?? []).join(", ") || "—",
      valorRegistrado: registradoBenef.get(b) ?? 0,
      valorQueTrava: travadoBenef.get(b) ?? 0,
      pctAgendaGrupo: agendaTotal > 0 ? (travadoBenef.get(b) ?? 0) / agendaTotal : null,
    }))
    .filter((g) => g.valorRegistrado > 0)
    .sort((a, b) => b.valorRegistrado - a.valorRegistrado);

  const porFilialArr: LinhaFilial[] = Array.from(porFilial.entries())
    .map(([estabelecimento, v]) => ({
      estabelecimento,
      agenda: v.agenda,
      travado: v.travado,
      livre: v.agenda - v.travado,
      nGravames: v.nGravames,
      primeiroDaFila: v.prioMin,
      pctComprometimento: v.agenda > 0 ? v.travado / v.agenda : null,
    }))
    .sort((a, b) => b.agenda - a.agenda);

  const filaPorData = Array.from(porData.entries())
    .map(([data, v]) => ({ data, registrado: v.registrado, profundidadeMax: v.profundidadeMax }))
    .sort((a, b) => a.data.localeCompare(b.data));

  return {
    escopo,
    kpis,
    callouts,
    inventario,
    comparacao,
    travadoPorBeneficiario,
    filaPorData,
    porGravame,
    porFilial: porFilialArr,
    meuCnpj,
  };
}
