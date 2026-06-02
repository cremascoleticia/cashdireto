"""Testes do app web v0 — montar_visao (puro) + smoke da página de upload."""
import pytest

from cashdireto_worker import webapp


def _tipos(blocos):
    return [b["tipo"] for b in blocos]


def test_visao_radar_vira_labels_grafico_tabela():
    snap = {"indicador": "radar_recebiveis", "valor": 200.0, "detalhe": {
        "valor_livre": 100.0, "valor_comprometido": 50.0, "valor_constituido": 200.0,
        "nivel_comprometimento": 0.25,
        "por_janela": {"0_30": {"constituido": 200.0, "comprometido": 50.0}},
        "por_arranjo": [{"arranjo": "MCC", "valor_constituido": 200.0, "percentual": 1.0}],
    }}
    blocos = webapp.montar_visao([snap])
    assert _tipos(blocos) == ["labels", "grafico", "tabela"]
    assert blocos[1]["labels"] == ["0_30"]
    assert blocos[2]["linhas"][0][0] == "MCC"


def test_visao_escalar_vira_label():
    blocos = webapp.montar_visao([{"indicador": "ap013c_total_suficiencia_depois",
                                   "valor": 200.0, "detalhe": None}])
    assert blocos[0]["tipo"] == "labels"
    assert blocos[0]["itens"][0]["valor"] == 200.0


def test_visao_grupos_vira_tabela():
    snap = {"indicador": "ap005_efeito_por_beneficiario", "valor": 65.0,
            "detalhe": {"total": 65.0, "grupos": [{"beneficiario_doc": "B1", "valor": 40.0},
                                                  {"beneficiario_doc": "B2", "valor": 25.0}]}}
    blocos = webapp.montar_visao([snap])
    assert blocos[0]["tipo"] == "tabela"
    assert "valor" in blocos[0]["colunas"] and len(blocos[0]["linhas"]) == 2


def test_visao_grafico_por_mes():
    snap = {"indicador": "ap013_onerado_por_uf_mes_oneracao", "valor": None,
            "detalhe": {"total": 50.0, "grupos": [
                {"usuario_final_doc": "U1", "ano_mes": "2026-06", "indicador_oneracao": "1", "valor": 40.0},
                {"usuario_final_doc": "U1", "ano_mes": "2026-07", "indicador_oneracao": "1", "valor": 10.0}]}}
    blocos = webapp.montar_visao([snap])
    assert blocos[0]["tipo"] == "grafico"
    assert blocos[0]["labels"] == ["2026-06", "2026-07"]
    assert blocos[0]["datasets"][0]["dados"] == [40.0, 10.0]


def test_pagina_upload_responde():
    fastapi = pytest.importorskip("fastapi")        # pula se as deps web não estiverem instaladas
    from fastapi.testclient import TestClient
    client = TestClient(webapp.criar_app())
    resp = client.get("/")
    assert resp.status_code == 200 and "Upload de arquivos" in resp.text
