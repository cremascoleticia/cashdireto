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


# ───────── Estoque / oneração (AP005) ─────────

def test_estoque_e_pct_onerado():
    urs = [{"valor_constituido_total": 500}, {"valor_constituido_total": 300}]
    pags = [{"valor_onerado": 500}, {"valor_onerado": 200}]
    assert _close(c.estoque_total(urs)[0], 800)
    assert _close(c.estoque_onerado(pags)[0], 700)
    assert _close(c.pct_onerado(urs, pags)[0], 0.875)       # 700/800


def test_onerado_proprio_e_terceiros():
    pags = [{"valor_onerado": 500, "beneficiario_doc": "X"},
            {"valor_onerado": 200, "beneficiario_doc": "Y"}]
    assert _close(c.onerado_proprio(pags, ["X"])[0], 500)
    assert _close(c.onerado_terceiros(pags, ["X"])[0], 200)


def test_onerado_proprio_sem_parametro_indisponivel():
    pags = [{"valor_onerado": 500, "beneficiario_doc": "X"}]
    valor, det = c.onerado_proprio(pags, None)
    assert valor is None and "detentor_proprio" in det["motivo"]   # não estima em silêncio


# ───────── Cobertura / headroom (AP013C) ─────────

def test_cobertura_e_headroom_redistribuicao():
    rows = [
        {"valor_minimo_a_manter": 1000, "valor_constituido_efeitos_depois": 1000,
         "valor_suficiencia_depois": 0, "valor_suficiencia_antes": 200},
        {"valor_minimo_a_manter": 2000, "valor_constituido_efeitos_depois": 1800,
         "valor_suficiencia_depois": 200, "valor_suficiencia_antes": 500},
    ]
    assert _close(c.cobertura_redistribuicao(rows)[0], 2800 / 3000)
    assert _close(c.headroom_redistribuicao(rows)[0], 200)         # 0 + 200
    assert _close(c.efeito_redistribuicao(rows)[0], (0 + 200) - (200 + 500))


# ───────── Sobrecolateralização / aderência / prioridade ─────────

def test_sobrecolateralizacao_ponderada_por_saldo():
    rows = [{"indicador_sobrecolateralizacao": 1.5, "saldo_devedor": 1000},
            {"indicador_sobrecolateralizacao": 0.95, "saldo_devedor": 2000}]
    assert _close(c.sobrecolateralizacao(rows)[0], (1.5 * 1000 + 0.95 * 2000) / 3000)


def test_aderencia_oneracao():
    rows = [{"valor_efeitos_calculados_cerc": 1750, "valor_efeitos_calculados_credenciadoras": 1750},
            {"valor_efeitos_calculados_cerc": 480, "valor_efeitos_calculados_credenciadoras": 240}]
    assert _close(c.aderencia_oneracao(rows)[0], (1750 + 240) / (1750 + 480))


def test_prioridade_1_share():
    rows = [{"qtd_ur_prioridade_1": 4, "qtd_ur_prioridade_diferente_1": 2},
            {"qtd_ur_prioridade_1": 2, "qtd_ur_prioridade_diferente_1": 1}]
    assert _close(c.prioridade_1_share(rows)[0], 6 / 9)


# ───────── Catálogo ─────────

def test_catalogo_cobre_status_conhecidos():
    nomes = {x["nome"] for x in CATALOGO}
    assert {"concentracao_bandeira", "onerado_proprio", "raiox_raiz", "radar_recebiveis",
            "cobertura_redistribuicao"} <= nomes
    # concentracao_bandeira explicitamente indisponível (regra 9), com motivo
    bandeira = next(x for x in CATALOGO if x["nome"] == "concentracao_bandeira")
    assert bandeira["status"] == "indisponivel" and "arranjo" in bandeira["motivo"]
    # garante que os extras especulativos foram removidos
    assert {"hhi_credenciadora", "agenda_por_bucket", "hhi_bandeira"}.isdisjoint(nomes)
    # indicadores com parâmetro declaram qual
    assert all("parametro" in x for x in CATALOGO if x["status"] == "disponivel_com_parametro")
