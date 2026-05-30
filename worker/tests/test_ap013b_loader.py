from datetime import date
from pathlib import Path

from cashdireto_worker.parsers import ap013b
from cashdireto_worker.parsers.ap013b import loader

FIXTURE = Path(__file__).parent / "fixtures" / "ap013b_sample.csv"


def _res(filename="CERC-AP013B_53462828_20260605_0000001_ret.csv"):
    return ap013b.parse(FIXTURE.read_bytes(), original_filename=filename, fallback_date=date(2026, 5, 29))


def test_cinco_statements_idempotentes():
    sts = loader.gerar_statements(_res(), nome_original="AP013B.csv")
    assert len(sts) == 5
    assert sts[0].startswith("insert into core.titular") and "on conflict (cnpj) do nothing" in sts[0]
    assert "insert into core.fonte_arquivo" in sts[1] and "on conflict (sha256)" in sts[1]
    assert sts[2].startswith("delete from core.ap013b_contrato")
    assert sts[3].startswith("insert into core.ap013b_contrato")
    assert sts[4].startswith("insert into core.ap013b_credenciadora")


def test_fonte_multi_titular_sem_titular_id():
    fonte = loader.gerar_statements(_res(), nome_original="AP013B.csv")[1]
    assert "'AP013B'" in fonte
    assert "titular_id" not in fonte
    assert "'2026-06-05'::date" in fonte


def test_dois_titulares_distintos():
    titular = loader.gerar_statements(_res(), nome_original="AP013B.csv")[0]
    assert "('11111111000111')" in titular and "('33333333000133')" in titular
    assert titular.count("),") == 1


def test_contrato_resolve_titular_e_datas():
    contrato = loader.gerar_statements(_res(), nome_original="AP013B.csv")[3]
    assert "join core.titular t on t.cnpj = d.contratante_doc" in contrato
    for cast in ("d.data_criacao::date", "d.data_assinatura::date",
                 "d.data_vencimento::date", "d.data_ultima_atualizacao::date"):
        assert cast in contrato


def test_credenciadora_religa_e_inteiros():
    cred = loader.gerar_statements(_res(), nome_original="AP013B.csv")[4]
    assert "join core.ap013b_contrato c on c.fonte_id =" in cred and "c.linha = d.linha" in cred
    assert "'01027058000191'" in cred and "'01425787000104'" in cred
    # inteiros sem casa decimal, valores decimais com ponto
    assert "5, 1, 6, 1800.0" in cred                            # 16.3,16.4,16.5,16.6 da 1ª credenciadora


def test_escape_de_aspas_simples():
    from dataclasses import replace
    res = _res()
    res.contratos[0] = replace(res.contratos[0], referencia_externa="D'OURO")
    contrato = loader.gerar_statements(res, nome_original="x.csv")[3]
    assert "'D''OURO'" in contrato


def test_sem_credenciadoras_gera_quatro_statements():
    base = ["REF", "CTR", "11111111000111", "0", "", "P", "DET", "CART", "1", "2",
            "1000.00", "2026-01-05", "2026-01-10", "2027-01-10", "2026-05-20", "", "1.50"]  # col16 vazia
    res = ap013b.parse(";".join(base) + "\n", original_filename="x.csv", fallback_date=date(2026, 5, 29))
    sts = loader.gerar_statements(res, nome_original="x.csv")
    assert len(sts) == 4 and not any("ap013b_credenciadora" in s for s in sts)


def test_sql_unico_concatena_com_ponto_e_virgula():
    sql = loader.gerar_sql(_res(), nome_original="AP013B.csv")
    assert sql.count(";\n\n") == 4 and sql.rstrip().endswith(";")
