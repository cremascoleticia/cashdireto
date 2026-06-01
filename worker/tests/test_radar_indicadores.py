"""Testes de fórmula dos indicadores RADAR (Fase 2) — por situação, janela e arranjo.

A mesma função serve por estabelecimento e por raiz (muda só quais linhas entram).
"""
import math

from cashdireto_worker.indicadores import radar


def _close(a, b):
    return a is not None and math.isclose(a, b, rel_tol=1e-9)


ROWS = [
    {"situacao": "livre", "janela": "0_30", "arranjo": "MCC", "valor": 100.0},
    {"situacao": "comprometido", "janela": "0_30", "arranjo": "MCC", "valor": 30.0},
    {"situacao": "constituido", "janela": "0_30", "arranjo": "MCC", "valor": 200.0},
    {"situacao": "constituido", "janela": "31_60", "arranjo": "VCC", "valor": 100.0},
    {"situacao": "comprometido", "janela": "31_60", "arranjo": "VCC", "valor": 50.0},
]


def test_totais_por_situacao():
    r = radar.indicadores_radar(ROWS)
    assert r["valor_livre"] == 100.0
    assert r["valor_comprometido"] == 80.0           # 30 + 50
    assert r["valor_constituido"] == 300.0           # 200 + 100


def test_nivel_comprometimento_total():
    r = radar.indicadores_radar(ROWS)
    assert _close(r["nivel_comprometimento"], 80 / 300)


def test_por_janela_e_nivel_por_janela():
    j = radar.indicadores_radar(ROWS)["por_janela"]
    assert j["0_30"] == {"livre": 100.0, "comprometido": 30.0, "constituido": 200.0,
                         "nivel_comprometimento": 30 / 200}
    assert j["31_60"]["constituido"] == 100.0
    assert _close(j["31_60"]["nivel_comprometimento"], 50 / 100)


def test_por_arranjo_com_percentual():
    arr = {a["arranjo"]: a for a in radar.indicadores_radar(ROWS)["por_arranjo"]}
    assert arr["MCC"]["valor_constituido"] == 200.0 and _close(arr["MCC"]["percentual"], 200 / 300)
    assert arr["VCC"]["valor_constituido"] == 100.0 and _close(arr["VCC"]["percentual"], 100 / 300)
    # ordenado por valor desc
    assert [a["arranjo"] for a in radar.indicadores_radar(ROWS)["por_arranjo"]] == ["MCC", "VCC"]


def test_sem_constituido_nivel_none():
    rows = [{"situacao": "comprometido", "janela": "0_30", "arranjo": "MCC", "valor": 50.0}]
    r = radar.indicadores_radar(rows)
    assert r["valor_constituido"] == 0.0
    assert r["nivel_comprometimento"] is None        # não estima sem constituído
    assert r["por_janela"]["0_30"]["nivel_comprometimento"] is None
    assert r["por_arranjo"] == []                     # nada constituído → sem arranjo


def test_raiz_e_estabelecimento_usam_a_mesma_funcao():
    # por raiz = passar linhas de todos os estabelecimentos; resultado soma naturalmente
    extra = [{"situacao": "constituido", "janela": "0_30", "arranjo": "MCC", "valor": 100.0}]
    r = radar.indicadores_radar(ROWS + extra)
    assert r["valor_constituido"] == 400.0           # 300 + 100 do outro estabelecimento
