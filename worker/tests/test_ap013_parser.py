from datetime import date
from pathlib import Path

import pytest

from cashdireto_worker.parsers import ap013
from cashdireto_worker.parsers.ap013 import Ap013ParseError

FIXTURE = Path(__file__).parent / "fixtures" / "ap013_sample.csv"
FALLBACK = date(2026, 5, 29)

# 17 colunas mínimas para montar linhas de erro (col3 preenchida salvo onde o teste quer vazio)
_BASE = ["REF", "CTR", "11111111000111", "0", "", "P", "D", "2",
         "0", "0", "0", "2027-01-01", "", "", "1", "0.00", "1"]


def _linha(over=None):
    cols = list(_BASE)
    for idx, val in (over or {}).items():
        cols[idx] = val
    # quota campos que contêm o separador (como faz o CSV real nas colunas-lista)
    out = ['"' + c.replace('"', '""') + '"' if (";" in c or '"' in c) else c for c in cols]
    return ";".join(out) + "\n"


def _parse(filename="CERC-AP013_53462828_20260605_0000001_ret.csv"):
    return ap013.parse(FIXTURE.read_bytes(), original_filename=filename, fallback_date=FALLBACK)


def test_estrutura_geral():
    r = _parse()
    assert len(r.contratos) == 2
    assert r.contratantes == {"11111111000111", "33333333000133"}
    assert r.total_urs == 3
    assert [c.linha for c in r.contratos] == [1, 2]
    assert r.data_referencia == date(2026, 6, 5)


def test_contrato_campos():
    c0 = _parse().contratos[0]
    assert c0.referencia_externa == "REF001" and c0.identificador_contrato == "CTR001"
    assert c0.contratante_doc == "11111111000111" and c0.repactuacao == "0"
    assert c0.identificador_contrato_anterior is None
    assert c0.participante_doc == "04391007000132" and c0.detentor_doc == "01027058000191"
    assert c0.tipo_efeito == "2" and c0.saldo_devedor == 1000.0
    assert c0.limite_operacao_garantida == 1500.0 and c0.valor_a_manter == 800.0
    assert c0.data_vencimento == date(2027, 1, 10)
    assert c0.indicadores_consistencia_raw is None             # col14 vazia
    assert c0.qtd_ur_alcancadas == 2.0 and c0.valor_ur_alcancadas == 800.0
    assert c0.resultado_distribuicao_onus == "1"


def test_urs_alcancadas_com_prioridade():
    urs = _parse().contratos[0].urs
    assert len(urs) == 2
    u0, u1 = urs
    assert u0.ordem == 1 and u0.arranjo == "MCD" and u0.constituicao == "1"
    assert u0.valor_constituido_total == 500.0 and u0.valor_constituido_efeito == 500.0
    assert u0.indicador_oneracao == "1"                        # prioridade 1
    assert u0.regra_divisao == "1" and u0.referencia_externa == "REFUR1"
    assert u0.data_liquidacao == date(2026, 6, 1)
    assert u1.ordem == 2 and u1.indicador_oneracao == "2"      # prioridade 2


def test_segundo_contrato_repactuacao_e_col14_bruta():
    c1 = _parse().contratos[1]
    assert c1.contratante_doc == "33333333000133" and c1.repactuacao == "1"
    assert c1.identificador_contrato_anterior == "CTR000X"
    assert c1.tipo_efeito == "3" and len(c1.urs) == 1
    u = c1.urs[0]
    assert u.constituicao == "2" and u.indicador_oneracao == "0"   # insucesso
    assert u.regra_divisao == "2" and u.valor_onerado == 100.0
    # col14 preservada bruta, sem quebra estruturada
    assert c1.indicadores_consistencia_raw is not None
    assert "estabilidade_agenda" in c1.indicadores_consistencia_raw
    assert "dispersao:2359.50" in c1.indicadores_consistencia_raw


def test_data_referencia_fallback():
    assert _parse("AP013.csv").data_referencia == FALLBACK     # sem token de data válido


def test_numero_de_colunas_errado_falha():
    with pytest.raises(Ap013ParseError, match="colunas"):
        ap013.parse("a;b;c\n", original_filename="x.csv", fallback_date=FALLBACK)


def test_ur_com_mais_de_14_campos_falha():
    sub = ";".join(["x"] * 15)
    with pytest.raises(Ap013ParseError, match=">14"):
        ap013.parse(_linha({12: sub}), original_filename="x.csv", fallback_date=FALLBACK)


def test_contratante_vazio_falha():
    with pytest.raises(Ap013ParseError, match="col3"):
        ap013.parse(_linha({2: ""}), original_filename="x.csv", fallback_date=FALLBACK)


def test_arquivo_vazio_falha():
    with pytest.raises(Ap013ParseError, match="sem registros"):
        ap013.parse("\n", original_filename="x.csv", fallback_date=FALLBACK)
