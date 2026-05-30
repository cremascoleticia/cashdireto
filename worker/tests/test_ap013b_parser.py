from datetime import date
from pathlib import Path

import pytest

from cashdireto_worker.parsers import ap013b
from cashdireto_worker.parsers.ap013b import Ap013bParseError

FIXTURE = Path(__file__).parent / "fixtures" / "ap013b_sample.csv"
FALLBACK = date(2026, 5, 29)

# 17 colunas mínimas para montar linhas de erro
_BASE = ["REF", "CTR", "11111111000111", "0", "", "P", "DET", "CART", "1", "2",
         "1000.00", "2026-01-05", "2026-01-10", "2027-01-10", "2026-05-20", "", "1.50"]


def _linha(over=None):
    cols = list(_BASE)
    for idx, val in (over or {}).items():
        cols[idx] = val
    out = ['"' + c.replace('"', '""') + '"' if (";" in c or '"' in c) else c for c in cols]
    return ";".join(out) + "\n"


def _parse(filename="CERC-AP013B_53462828_20260605_0000001_ret.csv"):
    return ap013b.parse(FIXTURE.read_bytes(), original_filename=filename, fallback_date=FALLBACK)


def test_estrutura_geral():
    r = _parse()
    assert len(r.contratos) == 2
    assert r.contratantes == {"11111111000111", "33333333000133"}
    assert r.total_credenciadoras == 3
    assert [c.linha for c in r.contratos] == [1, 2]
    assert r.data_referencia == date(2026, 6, 5)


def test_contrato_campos_e_datas():
    c0 = _parse().contratos[0]
    assert c0.referencia_externa == "REF001" and c0.contratante_doc == "11111111000111"
    assert c0.repactuacao == "0" and c0.identificador_contrato_anterior is None
    assert c0.detentor_doc == "53462828000128" and c0.carteira == "CART_A"
    assert c0.tipo_servico == "1" and c0.tipo_efeito == "2"
    assert c0.saldo_devedor == 1000.0
    assert c0.data_criacao == date(2026, 1, 5)
    assert c0.data_assinatura == date(2026, 1, 10)
    assert c0.data_vencimento == date(2027, 1, 10)
    assert c0.data_ultima_atualizacao == date(2026, 5, 20)
    assert c0.indicador_sobrecolateralizacao == 1.50


def test_credenciadoras_com_prioridade():
    creds = _parse().contratos[0].credenciadoras
    assert len(creds) == 2
    c0, c1 = creds
    assert c0.ordem == 1 and c0.credenciadora_doc == "01027058000191"
    assert c0.qtd_ur_constituidas == 5 and isinstance(c0.qtd_ur_constituidas, int)
    assert c0.qtd_ur_nao_constituidas == 1 and c0.qtd_efeitos == 6
    assert c0.valor_efeitos_solicitados == 1800.0
    assert c0.valor_efeitos_calculados_cerc == 1750.0
    assert c0.valor_efeitos_calculados_credenciadoras == 1750.0
    assert c0.qtd_ur_prioridade_1 == 4 and c0.qtd_ur_prioridade_diferente_1 == 2
    assert c1.ordem == 2 and c1.credenciadora_doc == "01425787000104"
    assert c1.qtd_ur_nao_constituidas == 0                     # zero preservado


def test_segundo_contrato_repactuacao():
    c1 = _parse().contratos[1]
    assert c1.contratante_doc == "33333333000133" and c1.repactuacao == "1"
    assert c1.identificador_contrato_anterior == "CTR000X"
    assert c1.indicador_sobrecolateralizacao == 0.95
    assert len(c1.credenciadoras) == 1 and c1.credenciadoras[0].qtd_ur_prioridade_1 == 2


def test_data_referencia_fallback():
    assert _parse("AP013B.csv").data_referencia == FALLBACK


def test_numero_de_colunas_errado_falha():
    with pytest.raises(Ap013bParseError, match="colunas"):
        ap013b.parse("a;b;c\n", original_filename="x.csv", fallback_date=FALLBACK)


def test_credenciadora_com_mais_de_10_campos_falha():
    sub = ";".join(["x"] * 11)
    with pytest.raises(Ap013bParseError, match=">10"):
        ap013b.parse(_linha({15: sub}), original_filename="x.csv", fallback_date=FALLBACK)


def test_contratante_vazio_falha():
    with pytest.raises(Ap013bParseError, match="col3"):
        ap013b.parse(_linha({2: ""}), original_filename="x.csv", fallback_date=FALLBACK)


def test_arquivo_vazio_falha():
    with pytest.raises(Ap013bParseError, match="sem registros"):
        ap013b.parse("\n", original_filename="x.csv", fallback_date=FALLBACK)
