from datetime import date
from pathlib import Path

import pytest

from cashdireto_worker.parsers import raiox
from cashdireto_worker.parsers.raiox import RaioxParseError

FIXTURE = Path(__file__).parent / "fixtures" / "raiox_sample.html"
FALLBACK = date(2026, 5, 29)


def _parse(filename="RAIOX.html"):
    return raiox.parse(FIXTURE.read_bytes(), original_filename=filename, fallback_date=FALLBACK)


def _card(res, chave):
    return next(d for d in res.indicadores if d["chave"] == chave)


def test_cadastro():
    c = _parse().cadastro
    assert c["cnpj"] == "11.111.111/0001-11"
    assert c["razao_social"] == "EMPRESA EXEMPLO LTDA"
    assert c["natureza_juridica"] == "SOCIEDADE LIMITADA"
    assert c["setor_economico"] == "COMERCIO"
    assert c["situacao_cadastral"] == "ATIVA"


def test_cards_valores_exatos_do_aria_label():
    r = _parse()
    # monetários abreviados na tela → valor EXATO do aria-label
    assert _card(r, "faturamento_estimado")["valor"] == 1000.0
    assert _card(r, "agenda_mensal_media")["valor"] == 150.0
    assert _card(r, "historico_agenda")["valor"] == 300.0
    assert _card(r, "volume_antecipacao")["valor"] == 200.0
    # exato na tela + texto extra
    fmd = _card(r, "faturamento_medio_diario")
    assert fmd["valor"] == 18.26 and "setor" in fmd["texto_extra"]
    # percentuais / contagens / índice
    assert _card(r, "nivel_comprometimento")["valor"] == 0.0
    assert _card(r, "potencial_chargeback")["valor"] == 0.0
    assert _card(r, "constatacoes_criticas")["valor"] == 9.0
    assert _card(r, "fraudes_detectadas")["valor"] == 0.0
    assert _card(r, "indice_conformidade_risco")["valor"] == 100.0


def test_cards_definicoes_e_unidades():
    r = _parse()
    assert "estimativa de faturamento" in _card(r, "faturamento_estimado")["definicao"]
    assert "chargeback" in _card(r, "potencial_chargeback")["definicao"].lower()
    assert _card(r, "faturamento_estimado")["unidade"] == "reais"
    assert _card(r, "nivel_comprometimento")["unidade"] == "percentual"
    assert _card(r, "indice_conformidade_risco")["unidade"] == "indice"


def test_serie_reconcilia_e_identifica_series():
    r = _parse()
    assert r.reconciliacao["ok"] is True
    assert r.reconciliacao["soma_agenda"] == 300.0
    assert r.reconciliacao["soma_volume"] == 200.0
    assert len(r.serie_mensal) == 4  # 2 meses × 2 séries
    porchave = {(s["competencia"], s["serie"]): s["valor"] for s in r.serie_mensal}
    assert porchave[(date(2025, 5, 1), "agenda")] == 100.0
    assert porchave[(date(2025, 6, 1), "agenda")] == 200.0
    assert porchave[(date(2025, 5, 1), "volume_antecipacao")] == 50.0
    assert porchave[(date(2025, 6, 1), "volume_antecipacao")] == 150.0


def test_relacionamentos():
    r = _parse()
    socios = [x["nome"] for x in r.relacionamentos if x["tipo"] == "socio_comum"]
    ips = {x["nome"]: x["percentual"] for x in r.relacionamentos if x["tipo"] == "instituicao_pagamento"}
    fin = {x["nome"]: x["percentual"] for x in r.relacionamentos if x["tipo"] == "financiador"}
    assert socios == ["EMPRESA SOCIA A LTDA", "EMPRESA SOCIA B LTDA"]
    assert ips == {"IP UM S.A.": 99.0, "IP DOIS S.A.": 1.0}
    assert fin == {"FIN ALPHA S.A.": 80.0, "FIN BETA S.A.": 20.0}


def test_data_referencia():
    assert _parse("RAIOX.html").data_referencia == FALLBACK              # sem token
    assert _parse("RAIOX_20260131_x.html").data_referencia == date(2026, 1, 31)


def test_serie_que_nao_reconcilia_falha():
    # adultera o card Histórico de Agenda (aria-label) -> soma das barras não bate -> erro
    html = FIXTURE.read_text(encoding="utf-8").replace('aria-label="R$ 300,00"', 'aria-label="R$ 999,00"')
    with pytest.raises(RaioxParseError, match="reconcilia"):
        raiox.parse(html, original_filename="RAIOX.html", fallback_date=FALLBACK)
