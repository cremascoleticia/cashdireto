from datetime import date
from pathlib import Path

from cashdireto_worker.parsers import ap013c
from cashdireto_worker.parsers.ap013c import loader

FIXTURE = Path(__file__).parent / "fixtures" / "ap013c_sample.csv"


def _res(filename="CERC-AP013C_53462828_20260605_0000001_ret.csv"):
    return ap013c.parse(FIXTURE.read_bytes(), original_filename=filename, fallback_date=date(2026, 5, 29))


def test_quatro_statements_sem_filha():
    sts = loader.gerar_statements(_res(), nome_original="AP013C.csv")
    assert len(sts) == 4                                        # titular + fonte + delete + registro (sem filha)
    assert sts[0].startswith("insert into core.titular") and "on conflict (cnpj) do nothing" in sts[0]
    assert "insert into core.fonte_arquivo" in sts[1] and "on conflict (sha256)" in sts[1]
    assert sts[2].startswith("delete from core.ap013c_redistribuicao")
    assert sts[3].startswith("insert into core.ap013c_redistribuicao")


def test_fonte_multi_titular_sem_titular_id():
    fonte = loader.gerar_statements(_res(), nome_original="AP013C.csv")[1]
    assert "'AP013C'" in fonte
    assert "titular_id" not in fonte
    assert "'2026-06-05'::date" in fonte


def test_dois_titulares_distintos():
    titular = loader.gerar_statements(_res(), nome_original="AP013C.csv")[0]
    assert "('11111111000111')" in titular and "('33333333000133')" in titular
    assert titular.count("),") == 1


def test_registro_resolve_titular_e_datas():
    registro = loader.gerar_statements(_res(), nome_original="AP013C.csv")[3]
    assert "join core.titular t on t.cnpj = d.contratante_doc" in registro
    assert "d.data_redistribuicao::date" in registro
    assert "'ERRO_X agenda anomala detectada'" in registro      # observações livres


def test_escape_de_aspas_simples():
    from dataclasses import replace
    res = _res()
    res.registros[0] = replace(res.registros[0], observacoes="D'OURO")
    registro = loader.gerar_statements(res, nome_original="x.csv")[3]
    assert "'D''OURO'" in registro


def test_sql_unico_concatena_com_ponto_e_virgula():
    sql = loader.gerar_sql(_res(), nome_original="AP013C.csv")
    assert sql.count(";\n\n") == 3 and sql.rstrip().endswith(";")
