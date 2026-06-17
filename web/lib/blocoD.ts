/**
 * Bloco D — Contratos / Gravames (tabela-mestre). Grão = um contrato/gravame, agrupando os efeitos
 * de `core.ur_efeitos` por `contrato_id` (= identificador_cerc_contrato, col 12.16 do AP005).
 *
 * Registrado (Claim) = Σ valor_registrado (12.12); Captura = Σ valor_capturado (12.15).
 * Derivados: aproveitamento = captura/registrado; abrangência (grupo todo/parcial/1 filial);
 * status (Ativo/Órfão/Pontual). Vigência = min–max data_liquidacao do contrato.
 */
import { consultar } from "./db";

export type EscopoTipo = "estabelecimento" | "raiz" | "grupo";

export interface FiltrosD {
  escopoTipo: EscopoTipo;
  escopoValor: string | null;
  dataReferencia: string;
  status: "todos" | "ativo" | "orfao" | "pontual";
  ordem: "registrado" | "captura" | "aproveitamento";
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

export type StatusGravame = "Ativo" | "Órfão" | "Pontual";
export type Abrangencia = "Grupo todo" | "Parcial" | "1 filial";

export interface LinhaGravame {
  contrato: string;
  regra: string | null;
  tipoPagamento: string | null;
  beneficiario: string | null;
  prioMin: number | null;
  nCnpj: number;
  nArr: number;
  cobertDatasPct: number | null;
  registrado: number;
  captura: number;
  pctFluxo: number | null;
  aproveitamento: number | null;
  abrangencia: Abrangencia;
  status: StatusGravame;
  inicio: string | null;
  fim: string | null;
}

export interface ResultadoBlocoD {
  linhas: LinhaGravame[];
  totalRegistrado: number;
  totalCaptura: number;
  aproveitamentoGlobal: number | null;
  nGravames: number;
  nComCaptura: number;
  nOrfaos: number;
  distTipoTrava: { rotulo: string; n: number }[];
  distPosicao: { posicao: string; n: number }[];
  topGD1: { contrato: string; registrado: number; captura: number }[];
}

interface LinhaRaw {
  contrato_id: string;
  regra: string | null;
  tipo_pagamento: string | null;
  beneficiario: string | null;
  prio_min: number | null;
  n_cnpj: string;
  n_arr: string;
  n_datas: string;
  registrado: unknown;
  captura: unknown;
  inicio: string | null;
  fim: string | null;
}

function diasEntre(inicio: string | null, fim: string | null): number | null {
  if (!inicio || !fim) return null;
  const a = new Date(inicio + "T00:00:00").getTime();
  const b = new Date(fim + "T00:00:00").getTime();
  if (Number.isNaN(a) || Number.isNaN(b)) return null;
  return Math.round((b - a) / 86400000) + 1;
}

export async function getBlocoD(f: FiltrosD): Promise<ResultadoBlocoD> {
  const params: unknown[] = [f.dataReferencia];
  let escopoPred = "";
  if (f.escopoValor) {
    params.push(f.escopoValor);
    escopoPred = `and ${COLUNA_ESCOPO[f.escopoTipo]} = $2`;
  }

  // total de filiais e de datas no escopo (p/ abrangência e cobertura temporal)
  const [tot] = await consultar<{ n_filiais: string; n_datas: string }>(
    `select count(distinct estabelecimento_cnpj) n_filiais, count(distinct data_liquidacao) n_datas
     from core.ur_efeitos where data_referencia = $1 ${escopoPred}`,
    params,
  );
  const totalFiliais = Number(tot?.n_filiais) || 0;
  const totalDatas = Number(tot?.n_datas) || 0;

  // agenda total (Σ valor_ur por UR distinta) — p/ % do fluxo
  const [{ agenda }] = await consultar<{ agenda: string }>(
    `select coalesce(sum(valor_ur),0) agenda from (
        select distinct ur_id, valor_ur from core.ur_efeitos where data_referencia = $1 ${escopoPred}
     ) u`,
    params,
  );
  const agendaTotal = num(agenda);

  const raw = await consultar<LinhaRaw>(
    `select contrato_id,
            max(regra) regra, max(tipo_pagamento) tipo_pagamento,
            max(beneficiario_cnpj) beneficiario, min(prioridade) prio_min,
            count(distinct estabelecimento_cnpj) n_cnpj,
            count(distinct arranjo) n_arr,
            count(distinct data_liquidacao) n_datas,
            coalesce(sum(valor_registrado),0) registrado,
            coalesce(sum(valor_capturado),0) captura,
            to_char(min(data_liquidacao),'YYYY-MM-DD') inicio,
            to_char(max(data_liquidacao),'YYYY-MM-DD') fim
     from core.ur_efeitos
     where data_referencia = $1 ${escopoPred} and contrato_id is not null
     group by contrato_id`,
    params,
  );

  let linhas: LinhaGravame[] = raw.map((r) => {
    const registrado = num(r.registrado);
    const captura = num(r.captura);
    const nCnpj = Number(r.n_cnpj) || 0;
    const dias = diasEntre(r.inicio, r.fim);
    const abrangencia: Abrangencia =
      totalFiliais > 0 && nCnpj >= totalFiliais ? "Grupo todo" : nCnpj <= 1 ? "1 filial" : "Parcial";
    const status: StatusGravame =
      dias !== null && dias <= 2 ? "Pontual" : captura > 1e-6 ? "Ativo" : "Órfão";
    return {
      contrato: r.contrato_id,
      regra: r.regra,
      tipoPagamento: r.tipo_pagamento,
      beneficiario: r.beneficiario,
      prioMin: r.prio_min,
      nCnpj,
      nArr: Number(r.n_arr) || 0,
      cobertDatasPct: totalDatas > 0 ? (Number(r.n_datas) / totalDatas) * 100 : null,
      registrado,
      captura,
      pctFluxo: agendaTotal > 0 ? captura / agendaTotal : null,
      aproveitamento: registrado > 0 ? captura / registrado : null,
      abrangencia,
      status,
      inicio: r.inicio,
      fim: r.fim,
    };
  });

  // filtro de status
  const mapaStatus: Record<string, StatusGravame> = { ativo: "Ativo", orfao: "Órfão", pontual: "Pontual" };
  if (f.status !== "todos") linhas = linhas.filter((l) => l.status === mapaStatus[f.status]);

  // ordenação
  linhas.sort((a, b) => {
    if (f.ordem === "captura") return b.captura - a.captura;
    if (f.ordem === "aproveitamento") return (b.aproveitamento ?? -1) - (a.aproveitamento ?? -1);
    return b.registrado - a.registrado;
  });

  const totalRegistrado = linhas.reduce((s, l) => s + l.registrado, 0);
  const totalCaptura = linhas.reduce((s, l) => s + l.captura, 0);
  const nComCaptura = linhas.filter((l) => l.captura > 1e-6).length;
  const nOrfaos = linhas.filter((l) => l.status === "Órfão").length;

  const dist = (chave: (l: LinhaGravame) => string) => {
    const m = new Map<string, number>();
    for (const l of linhas) m.set(chave(l), (m.get(chave(l)) ?? 0) + 1);
    return Array.from(m.entries()).map(([rotulo, n]) => ({ rotulo, n }));
  };

  return {
    linhas,
    totalRegistrado,
    totalCaptura,
    aproveitamentoGlobal: totalRegistrado > 0 ? totalCaptura / totalRegistrado : null,
    nGravames: linhas.length,
    nComCaptura,
    nOrfaos,
    distTipoTrava: dist((l) => l.regra ?? "—"),
    distPosicao: dist((l) => (l.prioMin === null ? "—" : String(l.prioMin)))
      .map((x) => ({ posicao: x.rotulo, n: x.n }))
      .sort((a, b) => a.posicao.localeCompare(b.posicao, undefined, { numeric: true })),
    topGD1: linhas.slice(0, 12).map((l) => ({ contrato: l.contrato, registrado: l.registrado, captura: l.captura })),
  };
}
