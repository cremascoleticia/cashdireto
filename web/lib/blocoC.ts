/**
 * Bloco C — Gestão de garantia (visão do beneficiário, cascata por prioridade).
 *
 * Busca em `core.ur_efeitos` TODOS os efeitos das URs onde o beneficiário selecionado aparece
 * (no escopo do cedente + data), agrupa por UR e roda a cascata (web/lib/cascata.ts) para apurar,
 * por UR e no total: constituído (meu), a pagar por prioridade (meu), perda por subordinação e
 * aproveitamento. URs sem `valor_ur` ficam fora dos totais (status sem_saldo_informado — não estima).
 */
import { consultar } from "./db";
import {
  aPagarUR,
  classificar,
  constituidoBeneficiario,
  totalBeneficiario,
  type Efeito,
  type StatusEfeito,
  type UR,
} from "./cascata";

export type EscopoTipo = "estabelecimento" | "raiz" | "grupo";

export interface FiltrosC {
  beneficiario: string;
  escopoTipo: EscopoTipo;
  escopoValor: string | null; // null = todos os cedentes onde apareço
  dataReferencia: string; // YYYY-MM-DD
}

/** UR + metadados de exibição (campos extras são ignorados pela cascata, que tipa por UR). */
interface URComMeta extends UR {
  estabelecimento: string;
  dataLiquidacao: string | null;
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

interface LinhaUR {
  ur_id: string;
  estabelecimento_cnpj: string;
  data_liquidacao: string | null;
  valor_ur: unknown;
  prioridade: number | null;
  beneficiario_cnpj: string | null;
  valor_constituido: unknown;
}

export interface KpisC {
  efeitoConstituido: number; // Σ constituído (meu)
  oneradoTotalContexto: number; // Σ constituído de TODOS os efeitos das URs onde apareço
  aPagar: number; // Σ cascata (meu)
  aproveitamento: number | null; // a pagar / constituído
  perdaPorSubordinacao: number; // constituído − a pagar (URs com saldo)
  ursSemSaldo: number;
}

export interface LinhaTabelaC {
  ur_id: string;
  estabelecimento: string;
  dataLiquidacao: string | null;
  minhaPosicao: number | null;
  constituidoMeu: number;
  oneradoTotalUR: number;
  aPagarMeu: number | null;
  status: StatusEfeito;
}

export interface PontoGraficoC {
  data: string; // data_liquidacao (YYYY-MM-DD) ou "sem data"
  constituido: number;
  aPagar: number;
}

export interface ResultadoBlocoC {
  kpis: KpisC;
  grafico: PontoGraficoC[]; // G-C1: constituído × a pagar por data de liquidação
  tabela: LinhaTabelaC[];
}

/** Carrega as URs (com todos os efeitos) do escopo e devolve agrupadas. */
async function carregarURs(f: FiltrosC): Promise<URComMeta[]> {
  const col = COLUNA_ESCOPO[f.escopoTipo];
  const params: unknown[] = [f.dataReferencia, f.beneficiario];
  let escopoPred = "";
  if (f.escopoValor) {
    params.push(f.escopoValor);
    escopoPred = `and ${col} = $3`;
  }
  const sql = `
    select ur_id, estabelecimento_cnpj, to_char(data_liquidacao,'YYYY-MM-DD') data_liquidacao,
           valor_ur, prioridade, beneficiario_cnpj, valor_constituido
    from core.ur_efeitos
    where data_referencia = $1
      and ur_id in (
        select ur_id from core.ur_efeitos
        where data_referencia = $1 and beneficiario_cnpj = $2 ${escopoPred}
      )
    order by ur_id, prioridade asc nulls last`;
  const linhas = await consultar<LinhaUR>(sql, params);

  const mapa = new Map<string, URComMeta>();
  for (const l of linhas) {
    let ur = mapa.get(l.ur_id);
    if (!ur) {
      ur = {
        ur_id: l.ur_id,
        valor_ur: num(l.valor_ur),
        efeitos: [],
        estabelecimento: l.estabelecimento_cnpj,
        dataLiquidacao: l.data_liquidacao,
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
    }
  }
  return Array.from(mapa.values());
}

/** Menor prioridade (mais sênior) entre os efeitos do beneficiário na UR. */
function minhaPosicao(ur: UR, beneficiario: string): number | null {
  const prios = ur.efeitos
    .filter((e) => e.beneficiario_cnpj === beneficiario && e.prioridade !== null)
    .map((e) => e.prioridade as number);
  return prios.length ? Math.min(...prios) : null;
}

export async function getBlocoC(f: FiltrosC): Promise<ResultadoBlocoC> {
  const urs = await carregarURs(f);

  // KPIs (total no escopo)
  const t = totalBeneficiario(urs, f.beneficiario);
  const oneradoTotalContexto = urs.reduce((s, ur) => s + aPagarUR(ur).oneradoTotal, 0);
  const kpis: KpisC = {
    efeitoConstituido: t.constituido,
    oneradoTotalContexto,
    aPagar: t.aPagar,
    aproveitamento: t.aproveitamento,
    perdaPorSubordinacao: t.perdaPorSubordinacao,
    ursSemSaldo: t.ursSemSaldo,
  };

  // Tabela por UR + agregação do gráfico por data de liquidação
  const tabela: LinhaTabelaC[] = [];
  const porData = new Map<string, PontoGraficoC>();
  for (const ur of urs) {
    const res = aPagarUR(ur);
    const constituidoMeu = constituidoBeneficiario(ur, f.beneficiario);
    const aPagarMeu =
      res.status === "sem_saldo_informado"
        ? null
        : (res.aPagarPorBeneficiario.get(f.beneficiario) ?? 0);
    tabela.push({
      ur_id: ur.ur_id,
      estabelecimento: ur.estabelecimento,
      dataLiquidacao: ur.dataLiquidacao,
      minhaPosicao: minhaPosicao(ur, f.beneficiario),
      constituidoMeu,
      oneradoTotalUR: res.oneradoTotal,
      aPagarMeu,
      status: classificar(constituidoMeu, aPagarMeu),
    });
    const chave = ur.dataLiquidacao ?? "sem data";
    const ponto = porData.get(chave) ?? { data: chave, constituido: 0, aPagar: 0 };
    ponto.constituido += constituidoMeu;
    ponto.aPagar += aPagarMeu ?? 0;
    porData.set(chave, ponto);
  }

  const grafico = Array.from(porData.values()).sort((a, b) => a.data.localeCompare(b.data));
  // só URs onde eu de fato tenho efeito constituído entram na tabela
  const tabelaFiltrada = tabela
    .filter((r) => r.constituidoMeu > 0)
    .sort((a, b) => (a.dataLiquidacao ?? "9999").localeCompare(b.dataLiquidacao ?? "9999"));

  return { kpis, grafico, tabela: tabelaFiltrada };
}

// ───────────────────────── opções de filtro ─────────────────────────

export interface OpcoesFiltro {
  datas: string[];
  beneficiarios: { cnpj: string; total: number }[];
  estabelecimentos: string[];
  raizes: string[];
  grupos: string[];
}

/** Beneficiário padrão para uma data: o maior por constituído NAQUELA foto (evita default vazio). */
export async function beneficiarioPadrao(dataReferencia: string): Promise<string | null> {
  const r = await consultar<{ cnpj: string }>(
    `select beneficiario_cnpj cnpj from core.ur_efeitos
     where data_referencia = $1 and beneficiario_cnpj is not null
     group by beneficiario_cnpj order by coalesce(sum(valor_constituido),0) desc nulls last limit 1`,
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
      `select beneficiario_cnpj cnpj, coalesce(sum(valor_constituido),0) total
       from core.ur_efeitos where beneficiario_cnpj is not null
       group by beneficiario_cnpj order by total desc nulls last`,
    )
  ).map((r) => ({ cnpj: r.cnpj, total: num(r.total) ?? 0 }));

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
