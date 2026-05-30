from datetime import date
from pathlib import Path

import pytest

from cashdireto_worker.parsers import ap007
from cashdireto_worker.parsers.ap007 import Ap007ParseError

FIXTURE = Path(__file__).parent / "fixtures" / "ap007_sample.csv"
FALLBACK = date(2026, 5, 29)

# 22 colunas mínimas para montar linhas de erro (col4 preenchida salvo onde o teste quer vazio)
_BASE = ["C", "REF", "CTR", "11111111000111", "0", "", "P", "D", "2",
         "0", "0", "0", "2026-01-01", "2027-01-01", "1", "1", "", "C", "", "", "1", "1"]


def _linha(over=None):
    cols = list(_BASE)
    for idx, val in (over or {}).items():
        cols[idx] = val
    # quota campos que contêm o separador (como faz o CSV real nas colunas-lista)
    out = ['"' + c.replace('"', '""') + '"' if (";" in c or '"' in c) else c for c in cols]
    return ";".join(out) + "\n"


def _parse(filename="CERC-AP007_99999999_20260605_0000001_ret.csv"):
    return ap007.parse(FIXTURE.read_bytes(), original_filename=filename, fallback_date=FALLBACK)


def test_estrutura_geral():
    r = _parse()
    assert len(r.contratos) == 3
    assert r.contratantes == {"11111111000111", "33333333000133"}
    assert r.total_parcelas == 3
    assert sum(c.saldo_devedor for c in r.contratos) == 6000.0
    assert [c.linha for c in r.contratos] == [1, 2, 3]


def test_contrato_campos():
    c0 = _parse().contratos[0]
    assert c0.tipo_operacao == "C" and c0.referencia_externa == "REF001"
    assert c0.identificador_contrato == "CTR001" and c0.contratante_doc == "11111111000111"
    assert c0.repactuacao == "0" and c0.identificadores_contrato_anterior == []
    assert c0.participante_doc == "04391007000132" and c0.detentor_doc == "01027058000191"
    assert c0.tipo_efeito == "2"
    assert c0.saldo_devedor == 1000.0 and c0.limite_operacao_garantida == 1500.0
    assert c0.valor_a_manter == 800.0
    assert c0.data_assinatura == date(2026, 1, 10) and c0.data_vencimento == date(2027, 1, 10)
    assert c0.tipo_servico == "1" and c0.modalidade_operacao == "1"
    assert c0.carteira == "CART_A" and c0.tipo_avaliacao is None
    assert c0.taxa_juros == 20.53 and c0.indexador == "1" and c0.aceite_incondicional == "1"
    assert c0.parcelas == []                                     # modalidade=1 (rotativo) → sem parcelas


def test_repactuacao_lista_contratos_anteriores():
    c1 = _parse().contratos[1]
    assert c1.tipo_operacao == "A" and c1.repactuacao == "1"
    assert c1.identificadores_contrato_anterior == ["CTR000A", "CTR000B"]
    assert c1.tipo_efeito == "3" and c1.modalidade_operacao == "2"


def test_parcelas_parceladas():
    c1 = _parse().contratos[1]
    assert len(c1.parcelas) == 2
    p0, p1 = c1.parcelas
    assert p0.ordem == 1 and p0.data_parcela == date(2026, 3, 1) and p0.valor_parcela == 500.0
    assert p1.ordem == 2 and p1.data_parcela == date(2026, 4, 1) and p1.valor_parcela == 500.0


def test_terceiro_contrato_outro_titular():
    c2 = _parse().contratos[2]
    assert c2.tipo_operacao == "I" and c2.contratante_doc == "33333333000133"
    assert c2.tipo_efeito == "4"                                 # bloqueio judicial
    assert len(c2.parcelas) == 1 and c2.parcelas[0].valor_parcela == 1000.0
    assert c2.taxa_juros is None and c2.indexador is None and c2.aceite_incondicional is None


def test_data_referencia_do_nome_com_fallback():
    assert _parse().data_referencia == date(2026, 6, 5)          # token _20260605_ (ignora 99999999)
    assert _parse("AP007.csv").data_referencia == FALLBACK       # sem token de data válido


def test_numero_de_colunas_errado_falha():
    with pytest.raises(Ap007ParseError, match="colunas"):
        ap007.parse("a;b;c\n", original_filename="x.csv", fallback_date=FALLBACK)


def test_parcela_com_mais_de_2_campos_falha():
    linha = _linha({15: "2", 16: "2026-01-01;100.00;extra"})  # col16 (0-based) = coluna 17
    with pytest.raises(Ap007ParseError, match=">2"):
        ap007.parse(linha, original_filename="x.csv", fallback_date=FALLBACK)


def test_contratante_vazio_falha():
    linha = _linha({3: ""})                                      # col4 (0-based 3) vazia
    with pytest.raises(Ap007ParseError, match="col4"):
        ap007.parse(linha, original_filename="x.csv", fallback_date=FALLBACK)


def test_arquivo_vazio_falha():
    with pytest.raises(Ap007ParseError, match="sem registros"):
        ap007.parse("\n", original_filename="x.csv", fallback_date=FALLBACK)
