"""Testes do runner de indicadores (Fase 2, fatia 2) — montagem pura + geração de SQL."""
from datetime import date

from cashdireto_worker.indicadores import runner


CONTEXTO = {
    "loja": {
        "11111111000111": {
            "agenda_ur": [
                {"situacao": "constituido", "janela": "0_30", "arranjo": "MCC", "valor": 200.0},
                {"situacao": "comprometido", "janela": "0_30", "arranjo": "MCC", "valor": 50.0},
            ],
            "ap013c": [
                {"valor_constituido_efeitos_depois": 1000.0, "valor_suficiencia_depois": 200.0},
            ],
            "ap005_pagamento": [
                {"valor_onerado": 300.0, "beneficiario_doc": "PROP"},
                {"valor_onerado": 100.0, "beneficiario_doc": "OUTRO"},
            ],
        },
    },
    "grupo": {
        "11111111": {
            "raiox_dossies": [
                {"cnpj": "11.111.111/0001-11",
                 "indicadores": {"faturamento_estimado": 1000.0, "faturamento_medio_diario": 10.0,
                                 "volume_antecipacao": 200.0, "nivel_comprometimento": 0.2},
                 "serie_mensal": [], "relacionamentos": []},
            ],
        },
    },
    "parametros": {"11111111000111": {"detentor_proprio": ["PROP"]}},
}
DREF = date(2026, 6, 5)


def _por_nome(snaps, escopo):
    return {s["indicador"]: s for s in snaps if s["escopo"] == escopo}


def test_montar_snapshots_escopos_e_chaves():
    snaps = runner.montar_snapshots(CONTEXTO, DREF)
    assert all(s["data_referencia"] == DREF for s in snaps)
    lojas = {s["chave"] for s in snaps if s["escopo"] == "loja"}
    grupos = {s["chave"] for s in snaps if s["escopo"] == "grupo"}
    assert lojas == {"11111111000111"} and grupos == {"11111111"}


def test_radar_headline_e_detalhe():
    loja = _por_nome(runner.montar_snapshots(CONTEXTO, DREF), "loja")
    radar = loja["radar_recebiveis"]
    assert radar["valor"] == 200.0                              # headline = valor_constituido
    assert radar["detalhe"]["valor_comprometido"] == 50.0       # detalhe traz a estrutura toda


def test_ap013c_escalares():
    loja = _por_nome(runner.montar_snapshots(CONTEXTO, DREF), "loja")
    assert loja["ap013c_total_constituido_efeitos_depois"]["valor"] == 1000.0
    assert loja["ap013c_total_suficiencia_depois"]["valor"] == 200.0


def test_onerado_proprio_usa_parametro():
    loja = _por_nome(runner.montar_snapshots(CONTEXTO, DREF), "loja")
    assert loja["onerado_proprio"]["valor"] == 300.0           # só o beneficiário PROP
    assert loja["onerado_terceiros"]["valor"] == 100.0


def test_grupo_usa_raiox_agregado():
    grupo = _por_nome(runner.montar_snapshots(CONTEXTO, DREF), "grupo")
    assert "raiox_raiz" in grupo
    assert grupo["raiox_raiz"]["detalhe"]["indicadores"]["faturamento_estimado"] == 1000.0


def test_gerar_statements_delete_e_insert():
    snaps = runner.montar_snapshots(CONTEXTO, DREF)
    sts = runner.gerar_statements(snaps, DREF)
    assert sts[0].startswith("delete from core.indicador_snapshot where data_referencia = '2026-06-05'")
    assert all(s.startswith("insert into core.indicador_snapshot") for s in sts[1:])
    joined = "\n".join(sts)
    # loja resolve titular_id pelo cnpj; grupo grava cnpj_raiz e titular nulo
    assert "(select id from core.titular where cnpj = '11111111000111')" in joined
    assert "'grupo', '11111111'" in joined
    # detalhe vai como jsonb
    assert "::jsonb" in joined


def test_jsonb_escapa_e_serializa_datas():
    # detalhe com data (ex.: série mensal do RAIOX) deve serializar sem quebrar
    snaps = [{"escopo": "loja", "chave": "C", "indicador": "x", "valor": 1.0,
              "detalhe": {"quando": date(2026, 6, 1), "txt": "D'OURO"}, "data_referencia": DREF}]
    sql = "\n".join(runner.gerar_statements(snaps, DREF))
    assert "2026-06-01" in sql and "D''OURO" in sql            # data via default=str; aspas escapadas
