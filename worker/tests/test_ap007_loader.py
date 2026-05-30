from datetime import date
from pathlib import Path

from cashdireto_worker.parsers import ap007
from cashdireto_worker.parsers.ap007 import loader

FIXTURE = Path(__file__).parent / "fixtures" / "ap007_sample.csv"


def _res(filename="CERC-AP007_99999999_20260605_0000001_ret.csv"):
    return ap007.parse(FIXTURE.read_bytes(), original_filename=filename, fallback_date=date(2026, 5, 29))


def test_cinco_statements_idempotentes():
    sts = loader.gerar_statements(_res(), nome_original="AP007.csv")
    assert len(sts) == 5
    assert sts[0].startswith("insert into core.titular") and "on conflict (cnpj) do nothing" in sts[0]
    assert "insert into core.fonte_arquivo" in sts[1] and "on conflict (sha256)" in sts[1]
    assert sts[2].startswith("delete from core.ap007_contrato")     # reprocessável (cascade → parcela)
    assert sts[3].startswith("insert into core.ap007_contrato")
    assert sts[4].startswith("insert into core.ap007_parcela")


def test_fonte_multi_titular_sem_titular_id():
    fonte = loader.gerar_statements(_res(), nome_original="AP007.csv")[1]
    assert "'AP007'" in fonte
    assert "titular_id" not in fonte                                # multi-titular → titular_id nulo
    assert "'2026-06-05'::date" in fonte                            # data_referencia do nome


def test_dois_titulares_distintos_no_upsert():
    titular = loader.gerar_statements(_res(), nome_original="AP007.csv")[0]
    assert "('11111111000111')" in titular and "('33333333000133')" in titular
    assert titular.count("),") == 1                                 # exatamente 2 valores


def test_contrato_resolve_titular_e_array_de_anteriores():
    contrato = loader.gerar_statements(_res(), nome_original="AP007.csv")[3]
    assert "join core.titular t on t.cnpj = d.contratante_doc" in contrato
    assert "d.data_assinatura::date" in contrato and "d.data_vencimento::date" in contrato
    assert "array['CTR000A', 'CTR000B']::text[]" in contrato        # col6 → text[]
    assert contrato.count("NULL::text[]") == 0                      # array vazio vira NULL (sem ::text[])


def test_parcela_religa_ao_contrato_por_fonte_e_linha():
    parcela = loader.gerar_statements(_res(), nome_original="AP007.csv")[4]
    assert "join core.ap007_contrato c on c.fonte_id =" in parcela and "c.linha = d.linha" in parcela
    assert "d.data_parcela::date" in parcela


def test_escape_de_aspas_simples():
    from dataclasses import replace
    res = _res()
    res.contratos[0] = replace(res.contratos[0], referencia_externa="D'OURO")
    contrato = loader.gerar_statements(res, nome_original="x.csv")[3]
    assert "'D''OURO'" in contrato


def test_sem_parcelas_gera_quatro_statements():
    # contrato rotativo (modalidade 1) sem parcelas → não emite insert em ap007_parcela
    base = ["C", "REF", "CTR", "11111111000111", "0", "", "P", "D", "2",
            "0", "0", "0", "2026-01-01", "2027-01-01", "1", "1", "", "C", "", "", "1", "1"]
    res = ap007.parse(";".join(base) + "\n", original_filename="x.csv", fallback_date=date(2026, 5, 29))
    sts = loader.gerar_statements(res, nome_original="x.csv")
    assert len(sts) == 4 and not any("ap007_parcela" in s for s in sts)


def test_sql_unico_concatena_com_ponto_e_virgula():
    sql = loader.gerar_sql(_res(), nome_original="AP007.csv")
    assert sql.count(";\n\n") == 4 and sql.rstrip().endswith(";")
