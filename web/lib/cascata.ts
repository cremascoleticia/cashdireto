/**
 * Cascata de prioridade — núcleo de cálculo do cockpit (seção 5.2/5.3 do spec).
 *
 * Responde, por UR: dado o saldo disponível (`valor_ur`) e a fila de efeitos/gravames ordenada
 * por prioridade, quanto CADA beneficiário de fato recebe ("a pagar por prioridade"). O gravame
 * nominal (`valor_constituido`) pode ser maior do que a UR comporta; o que o sênior consome, some
 * para os de trás (perda por subordinação).
 *
 * Regras invioláveis aplicadas aqui:
 *  - `valor_ur` ausente (null) ⇒ NÃO calcular: status `sem_saldo_informado`, fora dos totais (5.3).
 *    Nunca presumir saldo.
 *  - Empate de prioridade na mesma UR ⇒ ratear o saldo proporcionalmente ao constituído de cada
 *    efeito empatado (5.2).
 *  - Função PURA: não toca em banco. O caller decide quais efeitos entram (ex.: filtrar não-ônus).
 *
 * Os valores monetários são tratados em float; arredonde só na apresentação (`arredondarMoeda`),
 * para não exibir lixo de ponto flutuante (critério de aceite).
 */

export type Regra = "fixo" | "percentual";

/** Um efeito/gravame sobre uma UR (uma linha de `ur_efeitos`, lado do efeito). */
export interface Efeito {
  /** Posição na fila (1 = primeiro a receber). Null = sem ordem de ônus → vai para o fim. */
  prioridade: number | null;
  /** CNPJ do credor/domicílio do efeito. */
  beneficiario_cnpj: string | null;
  /** Valor que o efeito reserva nesta UR (se %, já = % × valor_ur — col 12.15 do AP005). */
  valor_constituido: number;
}

/** Uma Unidade de Recebível com sua fila de efeitos. */
export interface UR {
  ur_id: string;
  /** Saldo disponível a liquidar. Null = não informado (status `sem_saldo_informado`). */
  valor_ur: number | null;
  efeitos: Efeito[];
}

export type StatusUR = "ok" | "sem_saldo_informado";

export interface ResultadoUR {
  ur_id: string;
  status: StatusUR;
  valor_ur: number | null;
  /** Σ constituído de TODOS os efeitos da UR (pode exceder valor_ur). "Valor onerado total". */
  oneradoTotal: number;
  /** A pagar por prioridade, por beneficiário (chave = CNPJ). Vazio se sem_saldo_informado. */
  aPagarPorBeneficiario: Map<string, number>;
}

/** Status de um efeito de um beneficiário numa UR (rótulos da seção 9 / Bloco C).
 *  "Subordinado" = havia saldo mas os seniores consumiram antes de mim.
 *  "Sem saldo"   = a UR foi reportada com valor_ur = 0 (a constituir / já liquidada) — não é
 *                  subordinação, simplesmente não há o que distribuir.
 *  "Sem saldo informado" = valor_ur ausente (NULL): fora dos totais, não estimado. */
export type StatusEfeito = "Integral" | "Parcial" | "Subordinado" | "Sem saldo" | "Sem saldo informado";

const EPS = 1e-6;

/** Arredonda moeda para centavos (apresentação). */
export function arredondarMoeda(v: number): number {
  return Math.round((v + Number.EPSILON) * 100) / 100;
}

/**
 * Agrupa os efeitos por prioridade e devolve os grupos ordenados por prioridade ASC.
 * Efeitos com prioridade nula vão para o fim (não têm ordem de ônus definida).
 */
function gruposPorPrioridade(efeitos: Efeito[]): Efeito[][] {
  const mapa = new Map<number | null, Efeito[]>();
  for (const e of efeitos) {
    const grupo = mapa.get(e.prioridade);
    if (grupo) grupo.push(e);
    else mapa.set(e.prioridade, [e]);
  }
  const chaves = Array.from(mapa.keys()).sort((a, b) => {
    if (a === null) return 1; // nulls por último
    if (b === null) return -1;
    return a - b;
  });
  return chaves.map((k) => mapa.get(k)!);
}

/**
 * Roda a cascata de uma UR e devolve o resultado completo (status, onerado total e o "a pagar"
 * por beneficiário). É a base de tudo no Bloco C.
 */
export function aPagarUR(ur: UR): ResultadoUR {
  const oneradoTotal = ur.efeitos.reduce(
    (s, e) => s + Math.max(0, e.valor_constituido),
    0,
  );
  const aPagarPorBeneficiario = new Map<string, number>();

  if (ur.valor_ur === null || ur.valor_ur === undefined) {
    return {
      ur_id: ur.ur_id,
      status: "sem_saldo_informado",
      valor_ur: null,
      oneradoTotal,
      aPagarPorBeneficiario,
    };
  }

  let saldo = ur.valor_ur;
  for (const grupo of gruposPorPrioridade(ur.efeitos)) {
    const somaConst = grupo.reduce((s, e) => s + Math.max(0, e.valor_constituido), 0);
    const disponivel = Math.max(0, saldo);
    const pagoGrupo = Math.min(somaConst, disponivel);
    if (somaConst > 0) {
      for (const e of grupo) {
        const c = Math.max(0, e.valor_constituido);
        // rateio proporcional ao constituído (empate); grupo de 1 ⇒ fração 1 ⇒ min(c, disponível)
        const pagoEfeito = pagoGrupo * (c / somaConst);
        if (e.beneficiario_cnpj !== null && pagoEfeito > 0) {
          aPagarPorBeneficiario.set(
            e.beneficiario_cnpj,
            (aPagarPorBeneficiario.get(e.beneficiario_cnpj) ?? 0) + pagoEfeito,
          );
        }
      }
    }
    saldo -= pagoGrupo;
  }

  return {
    ur_id: ur.ur_id,
    status: "ok",
    valor_ur: ur.valor_ur,
    oneradoTotal,
    aPagarPorBeneficiario,
  };
}

/**
 * "A pagar por prioridade" de UM beneficiário numa UR. Devolve `null` quando a UR está
 * `sem_saldo_informado` (não presumir — excluir dos totais).
 */
export function aPagarBeneficiario(ur: UR, beneficiario: string): number | null {
  const res = aPagarUR(ur);
  if (res.status === "sem_saldo_informado") return null;
  return res.aPagarPorBeneficiario.get(beneficiario) ?? 0;
}

/** Constituído de um beneficiário numa UR (Σ dos efeitos dele). */
export function constituidoBeneficiario(ur: UR, beneficiario: string): number {
  return ur.efeitos
    .filter((e) => e.beneficiario_cnpj === beneficiario)
    .reduce((s, e) => s + Math.max(0, e.valor_constituido), 0);
}

/** Classifica o efeito do beneficiário na UR (rótulos do Bloco C).
 *  `valorUr` (opcional) distingue UR zerada (Sem saldo) de subordinação real. */
export function classificar(
  constituido: number,
  aPagar: number | null,
  valorUr?: number | null,
): StatusEfeito {
  if (aPagar === null) return "Sem saldo informado"; // valor_ur NULL
  if (valorUr !== undefined && valorUr !== null && valorUr <= EPS && constituido > EPS)
    return "Sem saldo"; // UR reportada zerada (a constituir) — não é subordinação
  if (constituido <= EPS) return "Subordinado"; // nada constituído ⇒ nada a receber
  if (aPagar <= EPS) return "Subordinado"; // havia saldo, sêniores consumiram
  if (aPagar >= constituido - EPS) return "Integral";
  return "Parcial";
}

export interface TotalBeneficiario {
  /** Σ a pagar por prioridade nas URs com saldo informado. */
  aPagar: number;
  /** Σ constituído (meu) em todas as URs do escopo. */
  constituido: number;
  /** Perda por subordinação = constituído − a pagar (nas URs com saldo). */
  perdaPorSubordinacao: number;
  /** Aproveitamento = a pagar / constituído (null se constituído 0). */
  aproveitamento: number | null;
  /** URs ignoradas por não terem saldo informado (5.3) — contabilizadas à parte, nunca estimadas. */
  ursSemSaldo: number;
}

/**
 * Agrega o "a pagar por prioridade" de um beneficiário sobre várias URs (escopo do Bloco C).
 * URs sem saldo informado são contadas em `ursSemSaldo` e ficam FORA dos totais de a-pagar.
 */
export function totalBeneficiario(urs: UR[], beneficiario: string): TotalBeneficiario {
  let aPagar = 0;
  let constituido = 0;
  let constituidoComSaldo = 0;
  let ursSemSaldo = 0;
  for (const ur of urs) {
    const res = aPagarUR(ur);
    const cBenef = constituidoBeneficiario(ur, beneficiario);
    constituido += cBenef;
    if (res.status === "sem_saldo_informado") {
      if (cBenef > 0) ursSemSaldo += 1;
      continue;
    }
    aPagar += res.aPagarPorBeneficiario.get(beneficiario) ?? 0;
    constituidoComSaldo += cBenef;
  }
  return {
    aPagar,
    constituido,
    perdaPorSubordinacao: constituidoComSaldo - aPagar,
    aproveitamento: constituido > EPS ? aPagar / constituido : null,
    ursSemSaldo,
  };
}
