"""Testes de fórmula dos indicadores (Fase 2) — Python puro, sem banco.

Entradas são linhas canônicas no formato das tabelas core.* (dicts), com valores escolhidos
para asserção exata. A LLM nunca calcula: estes testes são a garantia de que o número é correto.
"""
import math

from cashdireto_worker.indicadores import calculos as c
from cashdireto_worker.indicadores import CATALOGO


def _close(a, b):
    return a is not None and math.isclose(a, b, rel_tol=1e-9)


# (RADAR — totais por situação/janela/arranjo — fica em test_radar_indicadores.py)


# ───────── Oneração própria × terceiros (AP005) — métrica de risco ─────────
# (somas agrupadas de AP005 ficam em test_ap005_indicadores.py)

def test_onerado_proprio_e_terceiros():
    pags = [{"valor_onerado": 500, "beneficiario_doc": "X"},
            {"valor_onerado": 200, "beneficiario_doc": "Y"}]
    assert _close(c.onerado_proprio(pags, ["X"])[0], 500)
    assert _close(c.onerado_terceiros(pags, ["X"])[0], 200)


def test_onerado_proprio_sem_parametro_indisponivel():
    pags = [{"valor_onerado": 500, "beneficiario_doc": "X"}]
    valor, det = c.onerado_proprio(pags, None)
    assert valor is None and "detentor_proprio" in det["motivo"]   # não estima em silêncio


# (AP013/AP013B/AP013C — definições da área — ficam em test_ap013_indicadores.py)


# ───────── Catálogo ─────────

def test_catalogo_cobre_status_conhecidos():
    nomes = {x["nome"] for x in CATALOGO}
    assert {"concentracao_bandeira", "onerado_proprio", "raiox_raiz", "radar_recebiveis",
            "ap013c_total_suficiencia_depois"} <= nomes
    # concentracao_bandeira explicitamente indisponível (regra 9), com motivo
    bandeira = next(x for x in CATALOGO if x["nome"] == "concentracao_bandeira")
    assert bandeira["status"] == "indisponivel" and "arranjo" in bandeira["motivo"]
    # garante que os extras especulativos foram removidos
    assert {"hhi_credenciadora", "agenda_por_bucket", "hhi_bandeira", "cobertura_redistribuicao",
            "headroom_redistribuicao", "efeito_redistribuicao", "sobrecolateralizacao",
            "aderencia_oneracao", "prioridade_1_share", "estoque_total"}.isdisjoint(nomes)
    # indicadores com parâmetro declaram qual
    assert all("parametro" in x for x in CATALOGO if x["status"] == "disponivel_com_parametro")
