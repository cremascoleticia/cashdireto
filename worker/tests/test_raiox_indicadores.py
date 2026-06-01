"""Testes de fórmula dos indicadores RAIOX (Fase 2) — por estabelecimento e por raiz de CNPJ.

Valores escolhidos para asserção exata, seguindo as definições fornecidas pela área.
"""
import math
from datetime import date

from cashdireto_worker.indicadores import raiox


def _close(a, b):
    return a is not None and math.isclose(a, b, rel_tol=1e-9)


# Dois estabelecimentos da MESMA raiz (11111111), matriz + filial.
ESTAB1 = {
    "cnpj": "11.111.111/0001-11",
    "indicadores": {"nivel_comprometimento": 0.2, "potencial_chargeback": 0.1,
                    "faturamento_medio_diario": 10.0, "faturamento_estimado": 1000.0,
                    "agenda_mensal_media": 150.0, "volume_antecipacao": 200.0,
                    "constatacoes_criticas": 9.0, "fraudes_detectadas": 0.0,
                    "indice_conformidade_risco": 100.0},
    "serie_mensal": [{"competencia": date(2025, 5, 1), "serie": "agenda", "valor": 100.0},
                     {"competencia": date(2025, 6, 1), "serie": "agenda", "valor": 200.0}],
    "relacionamentos": [{"tipo": "socio_comum", "nome": "S1", "percentual": None},
                        {"tipo": "socio_comum", "nome": "S2", "percentual": None},
                        {"tipo": "instituicao_pagamento", "nome": "A", "percentual": 99.0},
                        {"tipo": "instituicao_pagamento", "nome": "B", "percentual": 1.0},
                        {"tipo": "financiador", "nome": "F", "percentual": 80.0}],
}
ESTAB2 = {
    "cnpj": "11.111.111/0002-00",
    "indicadores": {"nivel_comprometimento": 0.4, "potencial_chargeback": 0.5,
                    "faturamento_medio_diario": 30.0, "faturamento_estimado": 3000.0,
                    "agenda_mensal_media": 450.0, "volume_antecipacao": 600.0,
                    "constatacoes_criticas": 1.0, "fraudes_detectadas": 2.0,
                    "indice_conformidade_risco": 90.0},
    "serie_mensal": [{"competencia": date(2025, 5, 1), "serie": "agenda", "valor": 300.0},
                     {"competencia": date(2025, 6, 1), "serie": "agenda", "valor": 400.0}],
    "relacionamentos": [{"tipo": "socio_comum", "nome": "S2", "percentual": None},
                        {"tipo": "socio_comum", "nome": "S3", "percentual": None},
                        {"tipo": "instituicao_pagamento", "nome": "A", "percentual": 50.0},
                        {"tipo": "instituicao_pagamento", "nome": "C", "percentual": 50.0},
                        {"tipo": "financiador", "nome": "F", "percentual": 100.0}],
}


def test_raiz_cnpj():
    assert raiox.raiz_cnpj("11.111.111/0001-11") == "11111111"
    assert raiox.raiz_cnpj("11111111000111") == "11111111"
    assert raiox.raiz_cnpj("") is None


def test_por_estabelecimento_passthrough():
    r = raiox.por_estabelecimento(ESTAB1)
    assert r["cnpj"] == "11.111.111/0001-11"
    assert r["indicadores"]["faturamento_estimado"] == 1000.0
    assert len(r["serie_mensal"]) == 2 and len(r["relacionamentos"]) == 5


def test_raiz_somas_simples():
    ind = raiox.agregar_por_raiz([ESTAB1, ESTAB2])["indicadores"]
    assert ind["faturamento_estimado"] == 4000.0
    assert ind["faturamento_medio_diario"] == 40.0
    assert ind["agenda_mensal_media"] == 600.0
    assert ind["volume_antecipacao"] == 800.0
    assert ind["constatacoes_criticas"] == 10.0
    assert ind["fraudes_detectadas"] == 2.0


def test_raiz_ponderado_por_fmd():
    ind = raiox.agregar_por_raiz([ESTAB1, ESTAB2])["indicadores"]
    # (0.2*10 + 0.4*30) / 40 = 14/40
    assert _close(ind["nivel_comprometimento"], 0.35)
    # (0.1*10 + 0.5*30) / 40 = 16/40
    assert _close(ind["potencial_chargeback"], 0.40)


def test_raiz_nao_agrega_indice_conformidade():
    ind = raiox.agregar_por_raiz([ESTAB1, ESTAB2])["indicadores"]
    assert "indice_conformidade_risco" not in ind          # decisão da área: só por estabelecimento


def test_raiz_serie_somada_por_mes():
    serie = raiox.agregar_por_raiz([ESTAB1, ESTAB2])["serie_mensal"]
    por = {(s["competencia"], s["serie"]): s["valor"] for s in serie}
    assert por[(date(2025, 5, 1), "agenda")] == 400.0       # 100 + 300
    assert por[(date(2025, 6, 1), "agenda")] == 600.0       # 200 + 400


def test_raiz_socios_dedup():
    socios = raiox.agregar_por_raiz([ESTAB1, ESTAB2])["socios"]
    assert socios == ["S1", "S2", "S3"]                     # S2 não duplica


def test_raiz_ip_ponderado_por_volume():
    ips = {x["nome"]: x["percentual"] for x in raiox.agregar_por_raiz([ESTAB1, ESTAB2])["instituicoes_pagamento"]}
    # vol total = 800. A: (99*200 + 50*600)/800 = 49800/800
    assert _close(ips["A"], 49800 / 800)                    # 62.25
    assert _close(ips["B"], (1 * 200) / 800)                # 0.25
    assert _close(ips["C"], (50 * 600) / 800)               # 37.5
    assert _close(ips["A"] + ips["B"] + ips["C"], 100.0)    # fecha em 100%


def test_raiz_financiadores_ponderado():
    fin = {x["nome"]: x["percentual"] for x in raiox.agregar_por_raiz([ESTAB1, ESTAB2])["financiadores"]}
    # F: (80*200 + 100*600)/800 = 76000/800 = 95
    assert _close(fin["F"], 95.0)


def test_ip_sem_volume_fica_indisponivel():
    e1 = {**ESTAB1, "indicadores": {**ESTAB1["indicadores"], "volume_antecipacao": 0.0}}
    e2 = {**ESTAB2, "indicadores": {**ESTAB2["indicadores"], "volume_antecipacao": 0.0}}
    ips = raiox.agregar_por_raiz([e1, e2])["instituicoes_pagamento"]
    assert all(x["percentual"] is None for x in ips)        # sem volume não estima percentual
