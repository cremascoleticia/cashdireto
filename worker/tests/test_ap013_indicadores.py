"""Testes de fórmula dos indicadores AP013/AP013B/AP013C (Fase 2)."""
from datetime import date

from cashdireto_worker.indicadores import ap013, ap013b, ap013c


# ───────── AP013 — nível UR ─────────

UR_ROWS = [
    {"usuario_final_doc": "U1", "data_liquidacao": date(2026, 6, 1), "indicador_oneracao": "1",
     "valor_constituido_total": 100.0, "valor_onerado": 40.0},
    {"usuario_final_doc": "U1", "data_liquidacao": date(2026, 7, 1), "indicador_oneracao": "2",
     "valor_constituido_total": 200.0, "valor_onerado": 60.0},
    {"usuario_final_doc": "U2", "data_liquidacao": date(2026, 6, 1), "indicador_oneracao": "1",
     "valor_constituido_total": 50.0, "valor_onerado": 10.0},
]


def test_constituido_por_usuario_final():
    r = ap013.constituido_por_usuario_final(UR_ROWS)
    por = {g["usuario_final_doc"]: g["valor"] for g in r["grupos"]}
    assert r["total"] == 350.0 and por == {"U1": 300.0, "U2": 50.0}


def test_constituido_por_usuario_final_e_oneracao():
    r = ap013.constituido_por_usuario_final_e_oneracao(UR_ROWS)
    por = {(g["usuario_final_doc"], g["indicador_oneracao"]): g["valor"] for g in r["grupos"]}
    assert por == {("U1", "1"): 100.0, ("U1", "2"): 200.0, ("U2", "1"): 50.0}


def test_onerado_por_usuario_final_e_oneracao():
    r = ap013.onerado_por_usuario_final_e_oneracao(UR_ROWS)
    por = {(g["usuario_final_doc"], g["indicador_oneracao"]): g["valor"] for g in r["grupos"]}
    assert r["total"] == 110.0 and por == {("U1", "1"): 40.0, ("U1", "2"): 60.0, ("U2", "1"): 10.0}


def test_onerado_por_usuario_final_data_oneracao():
    r = ap013.onerado_por_usuario_final_data_oneracao(UR_ROWS)
    por = {(g["usuario_final_doc"], g["ano_mes"], g["indicador_oneracao"]): g["valor"] for g in r["grupos"]}
    assert por[("U1", "2026-06", "1")] == 40.0
    assert por[("U1", "2026-07", "2")] == 60.0
    assert por[("U2", "2026-06", "1")] == 10.0


def test_constituido_por_usuario_final_data_oneracao():
    r = ap013.constituido_por_usuario_final_data_oneracao(UR_ROWS)
    por = {(g["usuario_final_doc"], g["ano_mes"], g["indicador_oneracao"]): g["valor"] for g in r["grupos"]}
    assert por[("U1", "2026-07", "2")] == 200.0


# ───────── AP013 — nível contrato (detentor próprio) ─────────

CONTRATO_ROWS = [
    {"contratante_doc": "C1", "detentor_doc": "PROP", "tipo_efeito": "2",
     "valor_a_manter": 1000.0, "data_vencimento": date(2027, 1, 10)},
    {"contratante_doc": "C1", "detentor_doc": "PROP", "tipo_efeito": "2",
     "valor_a_manter": 500.0, "data_vencimento": date(2027, 6, 10)},
    {"contratante_doc": "C2", "detentor_doc": "OUTRO", "tipo_efeito": "3",
     "valor_a_manter": 9999.0, "data_vencimento": date(2027, 1, 10)},
]


def test_valor_a_manter_proprio_filtra_detentor_e_agrupa():
    r = ap013.valor_a_manter_proprio_por_contratante_efeito(CONTRATO_ROWS, ["PROP"])
    assert r["total"] == 1500.0                                  # ignora o detentor OUTRO
    assert len(r["grupos"]) == 1
    g = r["grupos"][0]
    assert g["contratante_doc"] == "C1" and g["tipo_efeito"] == "2"
    assert g["valor_a_manter"] == 1500.0
    assert g["data_vencimento"] == ["2027-01-10", "2027-06-10"]


def test_valor_a_manter_sem_parametro_indisponivel():
    r = ap013.valor_a_manter_proprio_por_contratante_efeito(CONTRATO_ROWS, None)
    assert r["total"] is None and "detentor_proprio" in r["motivo"]


# ───────── AP013B ─────────

AP013B_CONTRATOS = [  # valor_efeitos_calculados_credenciadoras = soma das credenciadoras do contrato
    {"contratante_doc": "C1", "detentor_doc": "PROP", "tipo_efeito": "2",
     "valor_efeitos_calculados_credenciadoras": 1750.0},
    {"contratante_doc": "C1", "detentor_doc": "PROP", "tipo_efeito": "2",
     "valor_efeitos_calculados_credenciadoras": 250.0},
    {"contratante_doc": "C3", "detentor_doc": "OUTRO", "tipo_efeito": "2",
     "valor_efeitos_calculados_credenciadoras": 9999.0},
]


def test_ap013b_calculado_credenciadoras_proprio():
    r = ap013b.calculado_credenciadoras_proprio_por_contratante_efeito(AP013B_CONTRATOS, ["PROP"])
    assert r["total"] == 2000.0                                  # 1750 + 250, ignora OUTRO
    assert r["grupos"] == [{"contratante_doc": "C1", "tipo_efeito": "2", "valor": 2000.0}]


def test_ap013b_sem_parametro_indisponivel():
    r = ap013b.calculado_credenciadoras_proprio_por_contratante_efeito(AP013B_CONTRATOS, None)
    assert r["total"] is None and "detentor_proprio" in r["motivo"]


# ───────── AP013C ─────────

AP013C_ROWS = [
    {"valor_constituido_efeitos_depois": 1000.0, "valor_suficiencia_depois": 0.0},
    {"valor_constituido_efeitos_depois": 1800.0, "valor_suficiencia_depois": 200.0},
]


def test_ap013c_totais_depois_da_redistribuicao():
    assert ap013c.total_constituido_efeitos_depois(AP013C_ROWS) == 2800.0
    assert ap013c.total_suficiencia_depois(AP013C_ROWS) == 200.0
