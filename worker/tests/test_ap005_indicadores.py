"""Testes de fórmula dos indicadores AP005 (Fase 2) — nível UR e nível efeito.

A mesma função serve por estabelecimento e por raiz (muda só quais linhas entram).
"""
from datetime import date

from cashdireto_worker.indicadores import ap005


UR_ROWS = [
    {"usuario_final_doc": "U1", "titular_ur_doc": "T1", "data_liquidacao": date(2026, 6, 1),
     "valor_constituido_total": 100.0, "valor_livre": 20.0, "valor_total_ur": 120.0},
    {"usuario_final_doc": "U1", "titular_ur_doc": "T1", "data_liquidacao": date(2026, 7, 1),
     "valor_constituido_total": 200.0, "valor_livre": 30.0, "valor_total_ur": 230.0},
    {"usuario_final_doc": "U2", "titular_ur_doc": "T2", "data_liquidacao": date(2026, 6, 1),
     "valor_constituido_total": 50.0, "valor_livre": 5.0, "valor_total_ur": 55.0},
]

PAG_ROWS = [
    {"indicador_ordem_efeito": "1", "regra_divisao": "1", "tipo_informacao_pagamento": "2",
     "beneficiario_doc": "B1", "valor_onerado": 30.0, "valor_constituido_efeito": 30.0},
    {"indicador_ordem_efeito": "1", "regra_divisao": "2", "tipo_informacao_pagamento": "7",
     "beneficiario_doc": "B1", "valor_onerado": 10.0, "valor_constituido_efeito": 10.0},
    {"indicador_ordem_efeito": "2", "regra_divisao": "1", "tipo_informacao_pagamento": "2",
     "beneficiario_doc": "B2", "valor_onerado": 20.0, "valor_constituido_efeito": 25.0},
]


# ───────── Nível UR ─────────

def test_constituido_por_usuario_final_total_e_por_mes():
    r = ap005.constituido_por_usuario_final(UR_ROWS)
    assert r["total"] == 350.0
    assert r["grupos"]["U1"]["total"] == 300.0
    assert r["grupos"]["U1"]["por_mes"] == {"2026-06": 100.0, "2026-07": 200.0}
    assert r["grupos"]["U2"]["total"] == 50.0 and r["grupos"]["U2"]["por_mes"] == {"2026-06": 50.0}


def test_constituido_por_titular_ur():
    g = ap005.constituido_por_titular_ur(UR_ROWS)["grupos"]
    assert g["T1"]["total"] == 300.0 and g["T2"]["total"] == 50.0


def test_livre_e_total_ur_por_usuario_final():
    livre = ap005.livre_por_usuario_final(UR_ROWS)["grupos"]
    total_ur = ap005.total_ur_por_usuario_final(UR_ROWS)["grupos"]
    assert livre["U1"]["total"] == 50.0 and livre["U2"]["total"] == 5.0
    assert total_ur["U1"]["total"] == 350.0 and total_ur["U2"]["total"] == 55.0


# ───────── Nível efeito ─────────

def test_constituido_efeito_por_ordem():
    r = ap005.constituido_efeito_por_ordem(PAG_ROWS)
    por = {g["indicador_ordem_efeito"]: g["valor"] for g in r["grupos"]}
    assert r["total"] == 65.0 and por == {"1": 40.0, "2": 25.0}


def test_onerado_por_ordem_e_regra():
    r = ap005.onerado_por_ordem_e_regra(PAG_ROWS)
    por = {(g["indicador_ordem_efeito"], g["regra_divisao"]): g["valor"] for g in r["grupos"]}
    assert r["total"] == 60.0
    assert por == {("1", "1"): 30.0, ("1", "2"): 10.0, ("2", "1"): 20.0}


def test_onerado_por_tipo_info_e_regra():
    r = ap005.onerado_por_tipo_info_e_regra(PAG_ROWS)
    por = {(g["tipo_informacao_pagamento"], g["regra_divisao"]): g["valor"] for g in r["grupos"]}
    assert por == {("2", "1"): 50.0, ("7", "2"): 10.0}        # tipo 2/regra 1 = 30+20


def test_constituido_efeito_por_ordem_e_beneficiario():
    r = ap005.constituido_efeito_por_ordem_e_beneficiario(PAG_ROWS)
    por = {(g["indicador_ordem_efeito"], g["beneficiario_doc"]): g["valor"] for g in r["grupos"]}
    assert por == {("1", "B1"): 40.0, ("2", "B2"): 25.0}


def test_constituido_efeito_por_beneficiario():
    r = ap005.constituido_efeito_por_beneficiario(PAG_ROWS)
    por = {g["beneficiario_doc"]: g["valor"] for g in r["grupos"]}
    assert r["total"] == 65.0 and por == {"B1": 40.0, "B2": 25.0}
    # ordenado por valor desc
    assert [g["beneficiario_doc"] for g in r["grupos"]] == ["B1", "B2"]
