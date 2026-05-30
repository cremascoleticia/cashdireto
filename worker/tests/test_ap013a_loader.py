from datetime import date
from pathlib import Path

from cashdireto_worker.parsers import ap013a
from cashdireto_worker.parsers.ap013a import loader

FIXTURE = Path(__file__).parent / "fixtures" / "ap013a_sample.csv"


def _res(filename="CERC-AP013A_53462828_20260605_0000001_ret.csv"):
    return ap013a.parse(FIXTURE.read_bytes(), original_filename=filename, fallback_date=date(2026, 5, 29))


def test_tres_statements_sem_titular():
    sts = loader.gerar_statements(_res(), nome_original="AP013A.csv")
    assert len(sts) == 3                                        # fonte + delete + resumo (sem upsert de titular)
    assert "insert into core.fonte_arquivo" in sts[0] and "on conflict (sha256)" in sts[0]
    assert sts[1].startswith("delete from core.ap013a_resumo")  # reprocessável
    assert sts[2].startswith("insert into core.ap013a_resumo")


def test_nao_toca_em_titular():
    sql = loader.gerar_sql(_res(), nome_original="AP013A.csv")
    assert "core.titular" not in sql                            # AP013A não tem contratante/titular


def test_fonte_ap013a_sem_titular_id():
    fonte = loader.gerar_statements(_res(), nome_original="AP013A.csv")[0]
    assert "'AP013A'" in fonte
    assert "titular_id" not in fonte
    assert "'2026-06-05'::date" in fonte


def test_resumo_valores_e_inteiros():
    resumo = loader.gerar_statements(_res(), nome_original="AP013A.csv")[2]
    assert "cross join (select id from core.fonte_arquivo where sha256=" in resumo
    assert "'53462828000128'" in resumo and "'53462828000200'" in resumo
    # inteiros sem casa decimal; decimais com ponto
    assert "3, 2, 6000.0" in resumo                             # qtd_contratos, qtd_contratantes, saldo
    assert "1750.0" in resumo


def test_escape_de_aspas_simples():
    from dataclasses import replace
    res = _res()
    res.resumos[0] = replace(res.resumos[0], detentor_doc="D'OURO")
    resumo = loader.gerar_statements(res, nome_original="x.csv")[2]
    assert "'D''OURO'" in resumo


def test_sql_unico_concatena_com_ponto_e_virgula():
    sql = loader.gerar_sql(_res(), nome_original="AP013A.csv")
    assert sql.count(";\n\n") == 2 and sql.rstrip().endswith(";")
