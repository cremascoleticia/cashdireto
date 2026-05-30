from datetime import date
from pathlib import Path

import pytest

from cashdireto_worker.parsers import ap013a
from cashdireto_worker.parsers.ap013a import Ap013aParseError

FIXTURE = Path(__file__).parent / "fixtures" / "ap013a_sample.csv"
FALLBACK = date(2026, 5, 29)


def _parse(filename="CERC-AP013A_53462828_20260605_0000001_ret.csv"):
    return ap013a.parse(FIXTURE.read_bytes(), original_filename=filename, fallback_date=FALLBACK)


def test_estrutura_geral():
    r = _parse()
    assert len(r.resumos) == 2
    # mesma raiz de CNPJ (53462828), filiais distintas → dois detentores
    assert r.detentores == {"53462828000128", "53462828000200"}
    assert [x.linha for x in r.resumos] == [1, 2]
    assert r.data_referencia == date(2026, 6, 5)


def test_resumo_campos_e_tipos():
    r0 = _parse().resumos[0]
    assert r0.detentor_doc == "53462828000128"
    assert r0.qtd_contratos == 3 and isinstance(r0.qtd_contratos, int)
    assert r0.qtd_contratantes == 2
    assert r0.valor_saldo_devedor_total == 6000.0
    assert r0.qtd_ur_constituidas == 5 and r0.qtd_ur_nao_constituidas == 1
    assert r0.qtd_efeitos == 6
    assert r0.valor_efeitos_solicitados == 1800.0
    assert r0.valor_efeitos_calculados_cerc == 1750.0
    assert r0.valor_efeitos_calculados_credenciadoras == 1750.0


def test_segunda_linha():
    r1 = _parse().resumos[1]
    assert r1.detentor_doc == "53462828000200"
    assert r1.qtd_ur_nao_constituidas == 0          # zero preservado (não vira NULL)
    assert r1.valor_efeitos_calculados_cerc == 480.0


def test_data_referencia_fallback():
    assert _parse("AP013A.csv").data_referencia == FALLBACK   # sem token de data válido


def test_numero_de_colunas_errado_falha():
    with pytest.raises(Ap013aParseError, match="colunas"):
        ap013a.parse("a;b;c\n", original_filename="x.csv", fallback_date=FALLBACK)


def test_detentor_vazio_falha():
    linha = ";3;2;6000.00;5;1;6;1800.00;1750.00;1750.00\n"
    with pytest.raises(Ap013aParseError, match="col1"):
        ap013a.parse(linha, original_filename="x.csv", fallback_date=FALLBACK)


def test_inteiro_invalido_falha():
    linha = "53462828000128;abc;2;6000.00;5;1;6;1800.00;1750.00;1750.00\n"
    with pytest.raises(Ap013aParseError, match="inteiro"):
        ap013a.parse(linha, original_filename="x.csv", fallback_date=FALLBACK)


def test_arquivo_vazio_falha():
    with pytest.raises(Ap013aParseError, match="sem registros"):
        ap013a.parse("\n", original_filename="x.csv", fallback_date=FALLBACK)
