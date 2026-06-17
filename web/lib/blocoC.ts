/**
 * Bloco C — Gestão de garantia (visão do beneficiário).
 *
 * Modelo (decisão da área 2026-06-17): "Valor registrado" = valor_onerado (12.12, claim nominal);
 * "Valor que trava / a pagar" = valor_capturado (12.15, já direcionado ao beneficiário pela CERC).
 * Não re-derivamos a cascata para o número exibido — usamos o capturado real; a perda por
 * subordinação é registrado − capturado. (O módulo `cascata.ts` segue testado para o algoritmo 5.2.)
 */
import { consultar } from "./db";
import { classificar, type StatusEfeito } from "./cascata";

export type EscopoTipo = "estabelecimento" | "raiz" | "grupo";

export interface FiltrosC {
  beneficiario: string;
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

interface LinhaUR {
  ur_id: string;
  estabelecimento_cnpj: string;
  titular: string | null;
  arranjo: string | null;
  data_liquidacao: string | null;
  valor_ur: unknown;
  prioridade: number | null;
  beneficiario_cnpj: string | null;
  regra: string | null;
  valor_registrado: unknown;
  valor_capturado: unknown;
}

interface URAgg {
  ur_id: string;
  estabelecimento: string;
  titular: string | null;
  arranjo: string | null;
  dataLiquidacao: string | null;
  valorUr: number | null;
  registradoTotal: number; // Σ registrado de TODOS os efeitos da UR
  registradoMeu: number;
  capturadoMeu: number;
  minhaPosicao: number | null;
  prioridadeMaxUR: number | null; // p/ flag "credor além da 2ª posição"
  regra: string | null;
}

export interface KpisC {
  efeitoConstituido: number; // Σ registrado (meu) — "Valor registrado"
  oneradoTotalContexto: number; // Σ registrado de TODOS os efeitos das URs onde apareço
  aPagar: number; // Σ capturado (meu) — valor que trava / já direcionado
  aproveitamento: number | null; // capturado / registrado
  perdaPorSubordinacao: number; // registrado − capturado
  ursSemSaldo: number;
}

export interface LinhaTabelaC {
  ur_id: string;
  estabelecimento: string;
  titular: string | null;
  arranjo: string | null;
  dataLiquidacao: string | null;
  minhaPosicao: number | null;
  regra: string | null;
  constituidoMeu: number; // registrado (meu)
  oneradoTotalUR: number;
  aPagarMeu: number; // capturado (meu)
  credorAlem2a: boolean;
  status: StatusEfeito;
}

export interface PontoGraficoC {
  data: string;
  constituido: number; // registrado
  aPagar: number; // capturado
}

export interface ResultadoBlocoC {
  kpis: KpisC;
  grafico: PontoGraficoC[];
  tabela: LinhaTabelaC[];
}

async function carregarURs(f: FiltrosC): Promise<Map<string, URAgg>> {
  const params: unknown[] = [f.dataReferencia, f.beneficiario];
  let escopoPred = "";
  if (f.escopoValor) {
    params.push(f.escopoValor);
    escopoPred = `and ${COLUNA_ESCOPO[f.escopoTipo]} = $3`;
  }
  const sql = `
    select ur_id, estabelecimento_cnpj, titular, arranjo,
           to_char(data_liquidacao,'YYYY-MM-DD') data_liquidacao,
           valor_ur, prioridade, beneficiario_cnpj, regra, valor_registrado, valor_capturado
    from core.ur_efeitos
    where data_referencia = $1
      and ur_id in (
        select ur_id from core.ur_efeitos
        where data_referencia = $1 and beneficiario_cnpj = $2 ${escopoPred}
      )
    order by ur_id, prioridade asc nulls last`;
  const linhas = await consultar<LinhaUR>(sql, params);

  const mapa = new Map<string, URAgg>();
  for (const l of linhas) {
    let ur = mapa.get(l.ur_id);
    if (!ur) {
      ur = {
        ur_id: l.ur_id,
        estabelecimento: l.estabelecimento_cnpj,
        titular: l.titular,
        arranjo: l.arranjo,
        dataLiquidacao: l.data_liquidacao,
        valorUr: l.valor_ur === null || l.valor_ur === undefined ? null : num(l.valor_ur),
        registradoTotal: 0,
        registradoMeu: 0,
        capturadoMeu: 0,
        minhaPosicao: null,
        prioridadeMaxUR: null,
        regra: null,
      };
      mapa.set(l.ur_id, ur);
    }
    const reg = num(l.valor_registrado);
    ur.registradoTotal += reg;
    if (l.prioridade !== null)
      ur.prioridadeMaxUR = ur.prioridadeMaxUR === null ? l.prioridade : Math.max(ur.prioridadeMaxUR, l.prioridade);
    if (l.beneficiario_cnpj === f.beneficiario) {
      ur.registradoMeu += reg;
      ur.capturadoMeu += num(l.valor_capturado);
      if (l.prioridade !== null)
        ur.minhaPosicao = ur.minhaPosicao === null ? l.prioridade : Math.min(ur.minhaPosicao, l.prioridade);
      if (!ur.regra && l.regra) ur.regra = l.regra; // regra do meu efeito
    }
  }
  return mapa;
}

export async function getBlocoC(f: FiltrosC): Promise<ResultadoBlocoC> {
  const urs = Array.from((await carregarURs(f)).values());

  let efeitoConstituido = 0;
  let oneradoTotalContexto = 0;
  let aPagar = 0;
  let ursSemSaldo = 0;
  const tabela: LinhaTabelaC[] = [];
  const porData = new Map<string, PontoGraficoC>();

  for (const ur of urs) {
    oneradoTotalContexto += ur.registradoTotal;
    if (ur.registradoMeu <= 0) continue; // só URs onde tenho efeito registrado
    efeitoConstituido += ur.registradoMeu;
    aPagar += ur.capturadoMeu;
    if (ur.valorUr === null) ursSemSaldo += 1;

    // regra do meu efeito: recuperada na agregação simplificada -> derivar pela posição (não temos aqui),
    // então marcamos pelo registro; status compara registrado x capturado.
    const status = classificar(ur.registradoMeu, ur.capturadoMeu, ur.valorUr);
    tabela.push({
      ur_id: ur.ur_id,
      estabelecimento: ur.estabelecimento,
      titular: ur.titular,
      arranjo: ur.arranjo,
      dataLiquidacao: ur.dataLiquidacao,
      minhaPosicao: ur.minhaPosicao,
      regra: ur.regra ?? null,
      constituidoMeu: ur.registradoMeu,
      oneradoTotalUR: ur.registradoTotal,
      aPagarMeu: ur.capturadoMeu,
      credorAlem2a: (ur.prioridadeMaxUR ?? 0) > 2,
      status,
    });

    const chave = ur.dataLiquidacao ?? "sem data";
    const p = porData.get(chave) ?? { data: chave, constituido: 0, aPagar: 0 };
    p.constituido += ur.registradoMeu;
    p.aPagar += ur.capturadoMeu;
    porData.set(chave, p);
  }

  const kpis: KpisC = {
    efeitoConstituido,
    oneradoTotalContexto,
    aPagar,
    aproveitamento: efeitoConstituido > 0 ? aPagar / efeitoConstituido : null,
    perdaPorSubordinacao: efeitoConstituido - aPagar,
    ursSemSaldo,
  };
  const grafico = Array.from(porData.values()).sort((a, b) => a.data.localeCompare(b.data));
  const tabelaOrd = tabela.sort((a, b) => (a.dataLiquidacao ?? "9999").localeCompare(b.dataLiquidacao ?? "9999"));
  return { kpis, grafico, tabela: tabelaOrd };
}

// ───────────────────────── opções de filtro ─────────────────────────

export interface OpcoesFiltro {
  datas: string[];
  beneficiarios: { cnpj: string; total: number }[];
  estabelecimentos: string[];
  raizes: string[];
  grupos: string[];
}

export async function beneficiarioPadrao(dataReferencia: string): Promise<string | null> {
  const r = await consultar<{ cnpj: string }>(
    `select beneficiario_cnpj cnpj from core.ur_efeitos
     where data_referencia = $1 and beneficiario_cnpj is not null
     group by beneficiario_cnpj order by coalesce(sum(valor_registrado),0) desc nulls last limit 1`,
    [dataReferencia],
  );
  return r[0]?.cnpj ?? null;
}

export async function getOpcoesFiltro(): Promise<OpcoesFiltro> {
  const datas = (
    await consultar<{ d: string }>(
      "select distinct to_char(data_referencia,'YYYY-MM-DD') d from core.ur_efeitos order by d desc",
    )
  ).map((r) => r.d);

  const beneficiarios = (
    await consultar<{ cnpj: string; total: string }>(
      `select beneficiario_cnpj cnpj, coalesce(sum(valor_registrado),0) total
       from core.ur_efeitos where beneficiario_cnpj is not null
       group by beneficiario_cnpj order by total desc nulls last`,
    )
  ).map((r) => ({ cnpj: r.cnpj, total: num(r.total) }));

  const col = async (c: string) =>
    (
      await consultar<{ v: string }>(
        `select distinct ${c} v from core.ur_efeitos where ${c} is not null order by v`,
      )
    ).map((r) => r.v);

  return {
    datas,
    beneficiarios,
    estabelecimentos: await col("estabelecimento_cnpj"),
    raizes: await col("raiz_cnpj"),
    grupos: await col("grupo_economico"),
  };
}
