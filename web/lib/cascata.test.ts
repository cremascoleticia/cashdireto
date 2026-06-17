import { describe, it, expect } from "vitest";
import {
  aPagarUR,
  aPagarBeneficiario,
  classificar,
  constituidoBeneficiario,
  totalBeneficiario,
  type UR,
} from "./cascata";

const MEU = "11111111111111";
const SENIOR = "22222222222222";
const OUTRO = "33333333333333";

describe("cascata de prioridade (5.2/5.3)", () => {
  it("(a) único efeito prio 1 → a pagar = constituído", () => {
    const ur: UR = {
      ur_id: "u1",
      valor_ur: 1000,
      efeitos: [{ prioridade: 1, beneficiario_cnpj: MEU, valor_constituido: 600 }],
    };
    expect(aPagarBeneficiario(ur, MEU)).toBe(600);
    expect(classificar(600, aPagarBeneficiario(ur, MEU))).toBe("Integral");
  });

  it("(b) sênior consome a UR inteira → meu a pagar = 0 (Subordinado)", () => {
    const ur: UR = {
      ur_id: "u2",
      valor_ur: 500,
      efeitos: [
        { prioridade: 1, beneficiario_cnpj: SENIOR, valor_constituido: 500 },
        { prioridade: 2, beneficiario_cnpj: MEU, valor_constituido: 400 },
      ],
    };
    expect(aPagarBeneficiario(ur, SENIOR)).toBe(500);
    const meu = aPagarBeneficiario(ur, MEU);
    expect(meu).toBe(0);
    expect(classificar(constituidoBeneficiario(ur, MEU), meu)).toBe("Subordinado");
  });

  it("(c) saldo parcial → a pagar = saldo remanescente (Parcial)", () => {
    const ur: UR = {
      ur_id: "u3",
      valor_ur: 700,
      efeitos: [
        { prioridade: 1, beneficiario_cnpj: SENIOR, valor_constituido: 500 },
        { prioridade: 2, beneficiario_cnpj: MEU, valor_constituido: 400 },
      ],
    };
    // sênior leva 500; sobra 200 dos meus 400
    const meu = aPagarBeneficiario(ur, MEU);
    expect(meu).toBe(200);
    expect(classificar(400, meu)).toBe("Parcial");
  });

  it("(d) empate de prioridade → rateio proporcional ao constituído", () => {
    const ur: UR = {
      ur_id: "u4",
      valor_ur: 300,
      efeitos: [
        { prioridade: 1, beneficiario_cnpj: MEU, valor_constituido: 200 },
        { prioridade: 1, beneficiario_cnpj: OUTRO, valor_constituido: 600 },
      ],
    };
    // empate: soma constituída 800, saldo 300 ⇒ rateio 200/800 e 600/800
    expect(aPagarBeneficiario(ur, MEU)).toBeCloseTo(300 * (200 / 800), 6); // 75
    expect(aPagarBeneficiario(ur, OUTRO)).toBeCloseTo(300 * (600 / 800), 6); // 225
    // soma paga não excede o saldo
    const res = aPagarUR(ur);
    const somaPaga = Array.from(res.aPagarPorBeneficiario.values()).reduce((a, b) => a + b, 0);
    expect(somaPaga).toBeCloseTo(300, 6);
  });

  it("(10.d) trocar o beneficiário inverte os papéis (subordinado ↔ sênior)", () => {
    const base = (priMeu: number, priSenior: number): UR => ({
      ur_id: "u5",
      valor_ur: 500,
      efeitos: [
        { prioridade: priSenior, beneficiario_cnpj: SENIOR, valor_constituido: 500 },
        { prioridade: priMeu, beneficiario_cnpj: MEU, valor_constituido: 400 },
      ],
    });
    // sou subordinado (prio 2): recebo 0
    expect(aPagarBeneficiario(base(2, 1), MEU)).toBe(0);
    // viro sênior (prio 1): recebo integral; o outro fica subordinado
    const inv = base(1, 2);
    expect(aPagarBeneficiario(inv, MEU)).toBe(400);
    expect(aPagarBeneficiario(inv, SENIOR)).toBe(100); // sobra 100 dos 500
  });

  it("(5.3) valor_ur nulo → sem_saldo_informado, a pagar = null, fora dos totais", () => {
    const ur: UR = {
      ur_id: "u6",
      valor_ur: null,
      efeitos: [{ prioridade: 1, beneficiario_cnpj: MEU, valor_constituido: 600 }],
    };
    const res = aPagarUR(ur);
    expect(res.status).toBe("sem_saldo_informado");
    expect(res.oneradoTotal).toBe(600); // onerado total ainda é conhecido
    expect(aPagarBeneficiario(ur, MEU)).toBeNull();
    expect(classificar(600, aPagarBeneficiario(ur, MEU))).toBe("Sem saldo informado");
  });

  it("valor_ur = 0 (UR a constituir) → 'Sem saldo', NÃO 'Subordinado' (único sênior na fila)", () => {
    const ur: UR = {
      ur_id: "u-zero",
      valor_ur: 0,
      efeitos: [{ prioridade: 1, beneficiario_cnpj: MEU, valor_constituido: 2065.07 }],
    };
    const meu = aPagarBeneficiario(ur, MEU); // 0 (nada a distribuir)
    expect(meu).toBe(0);
    expect(classificar(2065.07, meu, ur.valor_ur)).toBe("Sem saldo");
    // sem o valor_ur no classificar, cairia em Subordinado (comportamento antigo)
    expect(classificar(2065.07, meu)).toBe("Subordinado");
  });

  it("prioridade nula vai para o fim da fila (não fura a ordem do ônus)", () => {
    const ur: UR = {
      ur_id: "u7",
      valor_ur: 500,
      efeitos: [
        { prioridade: null, beneficiario_cnpj: OUTRO, valor_constituido: 500 },
        { prioridade: 1, beneficiario_cnpj: MEU, valor_constituido: 500 },
      ],
    };
    expect(aPagarBeneficiario(ur, MEU)).toBe(500); // prio 1 recebe primeiro
    expect(aPagarBeneficiario(ur, OUTRO)).toBe(0); // null fica subordinado
  });
});

describe("agregação por beneficiário (Bloco C)", () => {
  it("soma a-pagar e separa URs sem saldo (não estima)", () => {
    const urs: UR[] = [
      {
        ur_id: "a",
        valor_ur: 1000,
        efeitos: [{ prioridade: 1, beneficiario_cnpj: MEU, valor_constituido: 600 }],
      },
      {
        ur_id: "b",
        valor_ur: 100,
        efeitos: [
          { prioridade: 1, beneficiario_cnpj: SENIOR, valor_constituido: 500 },
          { prioridade: 2, beneficiario_cnpj: MEU, valor_constituido: 400 },
        ],
      },
      {
        ur_id: "c",
        valor_ur: null, // sem saldo: meus 300 ficam fora do a-pagar
        efeitos: [{ prioridade: 1, beneficiario_cnpj: MEU, valor_constituido: 300 }],
      },
    ];
    const t = totalBeneficiario(urs, MEU);
    expect(t.aPagar).toBe(600); // 600 (a) + 0 (b, sênior consumiu) + (c fora)
    expect(t.constituido).toBe(1300); // 600 + 400 + 300
    expect(t.ursSemSaldo).toBe(1);
    // perda por subordinação só conta URs com saldo: (600+400) - 600 = 400
    expect(t.perdaPorSubordinacao).toBe(400);
    expect(t.aproveitamento).toBeCloseTo(600 / 1300, 6);
  });
});
