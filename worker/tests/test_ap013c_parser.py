from datetime import date
from pathlib import Path

import pytest

from cashdireto_worker.parsers import ap013c
from cashdireto_worker.parsers.ap013c import Ap013cParseError

FIXTURE = Path(__file__).parent / "fixtures" / "ap013c_sample.csv"
FALLBACK = date(2026, 5, 29)

# 19 colunas mínimas para montar linhas de erro
_BASE = ["2026-05-29", "REF", "11111111000111", "P", "CART", "1000.00", "200.00", "5", "1",
         "800.00", "500.00", "3", "0", "0.00", "6", "0", "1000.00", "", ""]


def _linha(over=None):
    cols = list(_BASE)
    for idx, val in (over or {}).items():
        cols[idx] = val
    out = ['"' + c.replace('"', '""') + '"' if (";" in c or '"' in c) else c for c in cols]
    return ";".join(out) + "\n"


def _parse(filename="CERC-AP013C_53462828_20260605_0000001_ret.csv"):
    return ap013c.parse(FIXTURE.read_bytes(), original_filename=filename, fallback_date=FALLBACK)


def test_estrutura_geral():
    r = _parse()
    assert len(r.registros) == 2
    assert r.contratantes == {"11111111000111", "33333333000133"}
    assert [x.linha for x in r.registros] == [1, 2]
    assert r.data_referencia == date(2026, 6, 5)              # do nome do arquivo


def test_campos_antes_e_depois():
    r0 = _parse().registros[0]
    assert r0.data_redistribuicao == date(2026, 5, 29)        # col1 (data de negócio)
    assert r0.referencia_externa == "REF001" and r0.contratante_doc == "11111111000111"
    assert r0.participante_doc == "04391007000132" and r0.carteira == "CART_A"
    assert r0.valor_minimo_a_manter == 1000.0
    # antes
    assert r0.valor_suficiencia_antes == 200.0
    assert r0.qtd_ur_constituidas_antes == 5 and isinstance(r0.qtd_ur_constituidas_antes, int)
    assert r0.qtd_ur_a_constituir_antes == 1
    assert r0.valor_constituido_efeitos_antes == 800.0
    # entrada
    assert r0.valor_livre_agenda_antes == 500.0
    assert r0.qtd_ur_constituidas_solicitadas == 3 and r0.qtd_ur_a_constituir_solicitadas == 0
    # depois (redistribuição zerou o déficit)
    assert r0.valor_suficiencia_depois == 0.0
    assert r0.qtd_ur_constituidas_depois == 6 and r0.qtd_ur_a_constituir_depois == 0
    assert r0.valor_constituido_efeitos_depois == 1000.0
    # opcionais
    assert r0.valor_agenda_anomala == 0.0
    assert r0.observacoes is None


def test_opcionais_preenchidos():
    r1 = _parse().registros[1]
    assert r1.contratante_doc == "33333333000133"
    assert r1.valor_agenda_anomala == 50.0
    assert r1.observacoes == "ERRO_X agenda anomala detectada"
    assert r1.valor_suficiencia_depois == 200.0


def test_data_referencia_fallback():
    assert _parse("AP013C.csv").data_referencia == FALLBACK


def test_numero_de_colunas_errado_falha():
    with pytest.raises(Ap013cParseError, match="colunas"):
        ap013c.parse("a;b;c\n", original_filename="x.csv", fallback_date=FALLBACK)


def test_contratante_vazio_falha():
    with pytest.raises(Ap013cParseError, match="col3"):
        ap013c.parse(_linha({2: ""}), original_filename="x.csv", fallback_date=FALLBACK)


def test_inteiro_invalido_falha():
    with pytest.raises(Ap013cParseError, match="inteiro"):
        ap013c.parse(_linha({7: "abc"}), original_filename="x.csv", fallback_date=FALLBACK)


def test_data_invalida_falha():
    with pytest.raises(Ap013cParseError, match="data"):
        ap013c.parse(_linha({0: "31/12/2026"}), original_filename="x.csv", fallback_date=FALLBACK)


def test_arquivo_vazio_falha():
    with pytest.raises(Ap013cParseError, match="sem registros"):
        ap013c.parse("\n", original_filename="x.csv", fallback_date=FALLBACK)
