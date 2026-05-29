from datetime import date
from pathlib import Path

import pytest

from cashdireto_worker.parsers import radar
from cashdireto_worker.parsers.radar import JANELAS, SITUACOES, RadarParseError

FIXTURE = Path(__file__).parent / "fixtures" / "radar_sample.csv"
FALLBACK = date(2026, 5, 29)


def _parse(filename="radar_sample.csv"):
    return radar.parse(FIXTURE.read_bytes(), original_filename=filename, fallback_date=FALLBACK)


def _lookup(res):
    """(estab, arranjo, janela, situacao) -> valor"""
    return {(r.estabelecimento_cnpj, r.arranjo, r.janela, r.situacao): r.valor for r in res.registros}


# ───────────────────────── estrutura / unpivot ─────────────────────────

def test_contagens():
    res = _parse()
    assert res.linhas_origem == 4                 # 4 linhas de dados no fixture
    assert len(res.registros) == 4 * 20           # 20 células por linha (todas, inclusive zeros)
    assert res.estabelecimentos == {"12345678000101", "12345678000102", "99887766000100"}


def test_todas_as_celulas_por_linha():
    res = _parse()
    # cada (estab, cred, arranjo) deve ter exatamente as 20 combinações situacao×janela
    chaves = {}
    for r in res.registros:
        chaves.setdefault((r.estabelecimento_cnpj, r.credenciadora_doc, r.arranjo), set()).add(
            (r.situacao, r.janela)
        )
    esperado = {(s, j) for s in SITUACOES for j in JANELAS}
    assert all(v == esperado for v in chaves.values())
    assert len(chaves) == 4


def test_valores_unpivot():
    v = _lookup(_parse())
    A = "12345678000101"
    # linha normal (soma bate, mas não testamos a relação — só transcrição fiel)
    assert v[(A, "MCC", "0_30", "constituido")] == 300
    assert v[(A, "MCC", "31_60", "livre")] == 50
    # anomalia: livre+comprometido (10+90=100) != constituido (80) — preservado fielmente
    assert v[(A, "VCC", "0_30", "livre")] == 10
    assert v[(A, "VCC", "0_30", "comprometido")] == 90
    assert v[(A, "VCC", "0_30", "constituido")] == 80
    # constituído sozinho (livre/comprometido zerados)
    B = "12345678000102"
    assert v[(B, "CBC", "31_60", "constituido")] == 34.18
    assert v[(B, "CBC", "31_60", "livre")] == 0
    assert v[(B, "CBC", "31_60", "comprometido")] == 0
    # linha toda zerada também é gravada
    C = "99887766000100"
    assert v[(C, "MCC", "0_30", "constituido")] == 0


def test_pre_sempre_presente_e_zero_no_fixture():
    res = _parse()
    pres = [r.valor for r in res.registros if r.situacao == "pre"]
    assert len(pres) == 4 * 5            # 4 linhas × 5 janelas
    assert all(x == 0 for x in pres)


def test_dominios_e_nao_negativos():
    res = _parse()
    for r in res.registros:
        assert r.janela in JANELAS
        assert r.situacao in SITUACOES
        assert r.valor >= 0


# ───────────────────────── data de referência ─────────────────────────

def test_data_extraida_do_nome():
    # nome CERC tem id (44198946) + data (20260515); deve pegar a data válida
    res = _parse("CERC-RADAR_44198946_20260515_0000003_ret.csv")
    assert res.data_referencia == date(2026, 5, 15)
    assert res.data_origem == "nome_arquivo"


def test_data_fallback_sem_token():
    res = _parse("RADAR.csv")
    assert res.data_referencia == FALLBACK
    assert res.data_origem == "fallback"


def test_data_fallback_quando_ambiguo():
    # duas datas válidas no nome → não adivinha → fallback
    res = _parse("x_20260101_20260202_ret.csv")
    assert res.data_referencia == FALLBACK
    assert res.data_origem == "fallback"


def test_data_fallback_data_impossivel():
    res = _parse("CERC_44198946_20269999_ret.csv")
    assert res.data_referencia == FALLBACK


# ───────────────────────── robustez / ausência de dados ─────────────────────────

def test_arquivo_vazio():
    with pytest.raises(RadarParseError, match="vazio"):
        radar.parse("", original_filename="RADAR.csv", fallback_date=FALLBACK)


def test_so_cabecalho_nao_quebra():
    # arquivo presente mas sem linhas de dados → 0 registros, sem exceção
    header = ",".join(radar.parser.EXPECTED_HEADER)
    res = radar.parse(header, original_filename="RADAR.csv", fallback_date=FALLBACK)
    assert res.registros == []
    assert res.linhas_origem == 0


def test_cabecalho_invalido():
    with pytest.raises(RadarParseError, match="cabeçalho inesperado"):
        radar.parse("col_a,col_b\n1,2", original_filename="RADAR.csv", fallback_date=FALLBACK)


def test_linha_malformada():
    header = ",".join(radar.parser.EXPECTED_HEADER)
    # linha de dados com 1 campo a menos
    linha_curta = ",".join(["12345678000101", "111", "CRED", "MCC"] + ["0"] * 19)  # 23, falta 1
    conteudo = f"{header}\n{linha_curta}"
    with pytest.raises(RadarParseError, match="número de campos"):
        radar.parse(conteudo, original_filename="RADAR.csv", fallback_date=FALLBACK)


def test_valor_negativo_rejeitado():
    header = ",".join(radar.parser.EXPECTED_HEADER)
    linha = ",".join(["12345678000101", "111", "CRED", "MCC", "-1"] + ["0"] * 19)
    with pytest.raises(RadarParseError, match="negativo"):
        radar.parse(f"{header}\n{linha}", original_filename="RADAR.csv", fallback_date=FALLBACK)


def test_sha256_estavel():
    a = _parse()
    b = _parse()
    assert a.sha256 == b.sha256 and len(a.sha256) == 64
