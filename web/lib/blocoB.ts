/**
 * Bloco B — Raio-X de colateral (foto do dia). Visão do CEDENTE.
 *
 * Modelo (decisão da área): registrado = valor_onerado (12.12, claim nominal); travado/capturado =
 * valor_capturado (12.15, já direcionado). Tudo deriva de core.ur_efeitos (AP005), sem cascata para
 * o número exibido. Colunas de contrato (vigência/% dias) ficam no Bloco D.
 */
import { consultar } from "./db";

export type EscopoTipo = "estabelecimento" | "raiz" | "grupo";

export interface FiltrosB {
  escopoTipo: EscopoTipo;
  escopoValor: string | null;
  dataReferencia: string;
}

const COLUNA_ESCOPO: Record<EscopoTipo, string> = {
  estabelecimento: "estabelecimento_cnpj",
  raiz: "raiz_cnpj",
  grupo: "grupo_economico",
};

function num(v: unknown): number {
  if (v === null || v === undefined) return 0;
  const n = typeof v === "number" ? v : Number(v);
  return Number.isNaN(n) ? 0 : n;
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
  valor_registrado: unknown;
  valor_capturado: unknown;
}

export interface KpisB {
  totalRegistrado: number;
  agendaTravada: number;
  pctQueTrava: number | null;
  agendaTotal: number;
  agendaLivre: number;
  pctAgendaLivre: number | null;
  pctAgendaTravada: number | null;
  primeiroDaFilaTravaPct: number | null;
}

export interface Callouts {
  concentracaoRegistradora: { registradora: string; pct: number } | null;
  gravamesOrfaos: number;
  ursFilaRasa: number;
  ursFilaRasaDesprotegidas: number;
  ursFilaProfunda: number; // prioridade máx > 2
  ursComSaldo: number;
  horizonteInicio: string | null;
  horizonteFim: string | null;
}

export interface Inventario {
  filiais: number;
  gravamesRegistrados: number;
  travaFixo: number;
  travaPercentual: number;
  gravamesGrupoTodo: number;
  gravamesUmaFilial: number;
  bandeiras: number;
  ursComSaldo: number;
  beneficiariosDistintos: number;
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
  comparacao: { rotulo: string; valor: number }[];
  travadoPorBeneficiario: BarraTravadoBenef[];
  distribuicaoPosicao: { posicao: string; n: number }[]; // distribuição por posição na fila
  filaPorData: { data: string; fixo: number; percentual: number; profundidadeMax: number }[];
  porFilial: LinhaFilial[];
  meuCnpj: string | null;
}

interface URAgg {
  valorUr: number;
  estabelecimento: string;
  registradora: string | null;
  arranjo: string | null;
  dataLiquidacao: string | null;
  registradoTotal: number;
  capturadoTotal: number;
  prioMin: number | null;
  prioMax: number | null;
  credores: Set<string>;
  fixo: number; // registrado fixo
  percentual: number; // registrado %
  capturadoSenior: number;
}

async function carregar(f: FiltrosB) {
  const params: unknown[] = [f.dataReferencia];
  let escopoPred = "";
  if (f.escopoValor) {
    params.push(f.escopoValor);
    escopoPred = `and ${COLUNA_ESCOPO[f.escopoTipo]} = $2`;
  }
  const sql = `
    select ur_id, estabelecimento_cnpj, arranjo, registradora,
           to_char(data_liquidacao,'YYYY-MM-DD') data_liquidacao,
           valor_ur, prioridade, beneficiario_cnpj, regra, valor_registrado, valor_capturado
    from core.ur_efeitos
    where data_referencia = $1 ${escopoPred}
    order by ur_id, prioridade asc nulls last`;
  return consultar<LinhaB>(sql, params);
}

async function getMeuCnpj(): Promise<string | null> {
  const r = await consultar<{ c: string }>(
    "select distinct unnest(detentor_proprio) c from core.parametro_titular limit 1",
  );
  return r[0]?.c ?? null;
}

export async function getBlocoB(f: FiltrosB): Promise<ResultadoBlocoB> {
  const linhas = await carregar(f);
  const meuCnpj = await getMeuCnpj();
  const escopo: "grupo" | "filial" = f.escopoTipo === "estabelecimento" && f.escopoValor ? "filial" : "grupo";

  // agrupa por UR
  const urs = new Map<string, URAgg>();
  const travadoBenef = new Map<string, number>();
  const registradoBenef = new Map<string, number>();
  const filiaisBenef = new Map<string, Set<string>>();
  const porRegistradora = new Map<string, number>();
  const posicao = new Map<number, number>();
  const bandeiras = new Set<string>();
  const beneficiarios = new Set<string>();

  for (const l of linhas) {
    let ur = urs.get(l.ur_id);
    if (!ur) {
      ur = {
        valorUr: num(l.valor_ur),
        estabelecimento: l.estabelecimento_cnpj,
        registradora: l.registradora,
        arranjo: l.arranjo,
        dataLiquidacao: l.data_liquidacao,
        registradoTotal: 0,
        capturadoTotal: 0,
        prioMin: null,
        prioMax: null,
        credores: new Set(),
        fixo: 0,
        percentual: 0,
        capturadoSenior: 0,
      };
      urs.set(l.ur_id, ur);
    }
    if (!l.beneficiario_cnpj) continue;
    const reg = num(l.valor_registrado);
    const cap = num(l.valor_capturado);
    ur.registradoTotal += reg;
    ur.capturadoTotal += cap;
    ur.credores.add(l.beneficiario_cnpj);
    if (l.regra === "fixo") ur.fixo += reg;
    else if (l.regra === "percentual") ur.percentual += reg;
    if (l.prioridade !== null) {
      ur.prioMin = ur.prioMin === null ? l.prioridade : Math.min(ur.prioMin, l.prioridade);
      ur.prioMax = ur.prioMax === null ? l.prioridade : Math.max(ur.prioMax, l.prioridade);
      posicao.set(l.prioridade, (posicao.get(l.prioridade) ?? 0) + 1);
    }
    travadoBenef.set(l.beneficiario_cnpj, (travadoBenef.get(l.beneficiario_cnpj) ?? 0) + cap);
    registradoBenef.set(l.beneficiario_cnpj, (registradoBenef.get(l.beneficiario_cnpj) ?? 0) + reg);
    if (!filiaisBenef.has(l.beneficiario_cnpj)) filiaisBenef.set(l.beneficiario_cnpj, new Set());
    filiaisBenef.get(l.beneficiario_cnpj)!.add(l.estabelecimento_cnpj);
    beneficiarios.add(l.beneficiario_cnpj);
    if (l.arranjo) bandeiras.add(l.arranjo);
  }

  // capturado do 1º da fila por UR (efeito de menor prioridade)
  for (const l of linhas) {
    if (!l.beneficiario_cnpj || l.prioridade === null) continue;
    const ur = urs.get(l.ur_id)!;
    if (ur.prioMin !== null && l.prioridade === ur.prioMin) ur.capturadoSenior += num(l.valor_capturado);
  }

  let totalRegistrado = 0;
  let agendaTravada = 0;
  let agendaTotal = 0;
  let primeiroDaFilaTrava = 0;
  let ursComSaldo = 0;
  let ursFilaRasa = 0;
  let ursFilaRasaDesprotegidas = 0;
  let ursFilaProfunda = 0;
  let travaFixo = 0;
  let travaPercentual = 0;
  let horizonteInicio: string | null = null;
  let horizonteFim: string | null = null;
  const porFilial = new Map<string, { agenda: number; travado: number; nGravames: number; prioMin: number | null }>();
  const porData = new Map<string, { fixo: number; percentual: number; profundidadeMax: number }>();

  for (const [, ur] of Array.from(urs)) {
    totalRegistrado += ur.registradoTotal;
    agendaTravada += ur.capturadoTotal;
    agendaTotal += ur.valorUr;
    primeiroDaFilaTrava += ur.capturadoSenior;
    if (ur.valorUr > 0) ursComSaldo += 1;
    if (ur.credores.size <= 2) {
      ursFilaRasa += 1;
      if (ur.valorUr <= 0) ursFilaRasaDesprotegidas += 1;
    }
    if ((ur.prioMax ?? 0) > 2) ursFilaProfunda += 1;
    travaFixo += ur.fixo > 0 ? 1 : 0;
    travaPercentual += ur.percentual > 0 ? 1 : 0;
    if (ur.registradora) porRegistradora.set(ur.registradora, (porRegistradora.get(ur.registradora) ?? 0) + ur.registradoTotal);

    const ff = porFilial.get(ur.estabelecimento) ?? { agenda: 0, travado: 0, nGravames: 0, prioMin: null };
    ff.agenda += ur.valorUr;
    ff.travado += ur.capturadoTotal;
    ff.nGravames += ur.credores.size;
    if (ur.prioMin !== null) ff.prioMin = ff.prioMin === null ? ur.prioMin : Math.min(ff.prioMin, ur.prioMin);
    porFilial.set(ur.estabelecimento, ff);

    const k = ur.dataLiquidacao ?? "sem data";
    const pd = porData.get(k) ?? { fixo: 0, percentual: 0, profundidadeMax: 0 };
    pd.fixo += ur.fixo;
    pd.percentual += ur.percentual;
    pd.profundidadeMax = Math.max(pd.profundidadeMax, ur.credores.size);
    porData.set(k, pd);

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

  let concentracaoRegistradora: Callouts["concentracaoRegistradora"] = null;
  if (totalRegistrado > 0 && porRegistradora.size) {
    const [reg, val] = Array.from(porRegistradora.entries()).sort((a, b) => b[1] - a[1])[0];
    concentracaoRegistradora = { registradora: reg, pct: val / totalRegistrado };
  }
  let gravamesOrfaos = 0;
  for (const [b, reg] of Array.from(registradoBenef)) {
    if (reg > 0 && (travadoBenef.get(b) ?? 0) <= 1e-6) gravamesOrfaos += 1;
  }

  let gravamesGrupoTodo = 0;
  let gravamesUmaFilial = 0;
  for (const fil of Array.from(filiaisBenef.values())) {
    if (fil.size > 1) gravamesGrupoTodo += 1;
    else gravamesUmaFilial += 1;
  }

  const callouts: Callouts = {
    concentracaoRegistradora,
    gravamesOrfaos,
    ursFilaRasa,
    ursFilaRasaDesprotegidas,
    ursFilaProfunda,
    ursComSaldo,
    horizonteInicio,
    horizonteFim,
  };
  const inventario: Inventario = {
    filiais: porFilial.size,
    gravamesRegistrados: travaFixo + travaPercentual,
    travaFixo,
    travaPercentual,
    gravamesGrupoTodo,
    gravamesUmaFilial,
    bandeiras: bandeiras.size,
    ursComSaldo,
    beneficiariosDistintos: beneficiarios.size,
  };

  const travadoPorBeneficiario = Array.from(travadoBenef.entries())
    .map(([beneficiario, travado]) => ({ beneficiario, travado, meu: beneficiario === meuCnpj }))
    .filter((x) => x.travado > 0)
    .sort((a, b) => b.travado - a.travado)
    .slice(0, 15);

  const distribuicaoPosicao = Array.from(posicao.entries())
    .sort((a, b) => a[0] - b[0])
    .slice(0, 12)
    .map(([p, n]) => ({ posicao: String(p), n }));

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
    .map(([data, v]) => ({ data, fixo: v.fixo, percentual: v.percentual, profundidadeMax: v.profundidadeMax }))
    .sort((a, b) => a.data.localeCompare(b.data));

  return {
    escopo,
    kpis,
    callouts,
    inventario,
    comparacao,
    travadoPorBeneficiario,
    distribuicaoPosicao,
    filaPorData,
    porFilial: porFilialArr,
    meuCnpj,
  };
}
