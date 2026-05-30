from datetime import date
from pathlib import Path

from cashdireto_worker.parsers import ap013
from cashdireto_worker.parsers.ap013 import loader

FIXTURE = Path(__file__).parent / "fixtures" / "ap013_sample.csv"


def _res(filename="CERC-AP013_53462828_20260605_0000001_ret.csv"):
    return ap013.parse(FIXTURE.read_bytes(), original_filename=filename, fallback_date=date(2026, 5, 29))


def test_cinco_statements_idempotentes():
    sts = loader.gerar_statements(_res(), nome_original="AP013.csv")
    assert len(sts) == 5
    assert sts[0].startswith("insert into core.titular") and "on conflict (cnpj) do nothing" in sts[0]
    assert "insert into core.fonte_arquivo" in sts[1] and "on conflict (sha256)" in sts[1]
    assert sts[2].startswith("delete from core.ap013_contrato")    # reprocessável (cascade → ur)
    assert sts[3].startswith("insert into core.ap013_contrato")
    assert sts[4].startswith("insert into core.ap013_ur")


def test_fonte_multi_titular_sem_titular_id():
    fonte = loader.gerar_statements(_res(), nome_original="AP013.csv")[1]
    assert "'AP013'" in fonte
    assert "titular_id" not in fonte                               # multi-titular → titular_id nulo
    assert "'2026-06-05'::date" in fonte


def test_dois_titulares_distintos_no_upsert():
    titular = loader.gerar_statements(_res(), nome_original="AP013.csv")[0]
    assert "('11111111000111')" in titular and "('33333333000133')" in titular
    assert titular.count("),") == 1


def test_contrato_resolve_titular_e_guarda_col14_bruta():
    contrato = loader.gerar_statements(_res(), nome_original="AP013.csv")[3]
    assert "join core.titular t on t.cnpj = d.contratante_doc" in contrato
    assert "d.data_vencimento::date" in contrato
    assert "indicadores_consistencia_raw" in contrato
    assert "estabilidade_agenda" in contrato                       # col14 bruta vai pro SQL


def test_ur_religa_ao_contrato_por_fonte_e_linha():
    ur = loader.gerar_statements(_res(), nome_original="AP013.csv")[4]
    assert "join core.ap013_contrato c on c.fonte_id =" in ur and "c.linha = d.linha" in ur
    assert "d.data_liquidacao::date" in ur
    assert "'REFUR1'" in ur and "'REFUR3'" in ur                   # URs de contratos distintos


def test_escape_de_aspas_simples():
    from dataclasses import replace
    res = _res()
    res.contratos[0] = replace(res.contratos[0], referencia_externa="D'OURO")
    contrato = loader.gerar_statements(res, nome_original="x.csv")[3]
    assert "'D''OURO'" in contrato


def test_sem_urs_gera_quatro_statements():
    base = ["REF", "CTR", "11111111000111", "0", "", "P", "D", "2",
            "0", "0", "0", "2027-01-01", "", "", "1", "0.00", "1"]   # col13 (idx 12) vazia
    res = ap013.parse(";".join(base) + "\n", original_filename="x.csv", fallback_date=date(2026, 5, 29))
    sts = loader.gerar_statements(res, nome_original="x.csv")
    assert len(sts) == 4 and not any("ap013_ur" in s for s in sts)


def test_sql_unico_concatena_com_ponto_e_virgula():
    sql = loader.gerar_sql(_res(), nome_original="AP013.csv")
    assert sql.count(";\n\n") == 4 and sql.rstrip().endswith(";")
