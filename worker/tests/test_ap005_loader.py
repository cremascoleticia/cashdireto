from datetime import date
from pathlib import Path

from cashdireto_worker.parsers import ap005
from cashdireto_worker.parsers.ap005 import loader

FIXTURE = Path(__file__).parent / "fixtures" / "ap005_sample.csv"


def _res(filename="CERC-AP005_99999999_20260605_0000001_ret.csv"):
    return ap005.parse(FIXTURE.read_bytes(), original_filename=filename, fallback_date=date(2026, 5, 29))


def test_cinco_statements_idempotentes():
    sts = loader.gerar_statements(_res(), nome_original="AP005.csv")
    assert len(sts) == 5
    assert sts[0].startswith("insert into core.titular") and "on conflict (cnpj) do nothing" in sts[0]
    assert "insert into core.fonte_arquivo" in sts[1] and "on conflict (sha256)" in sts[1]
    assert sts[2].startswith("delete from core.ap005_ur")          # reprocessável (cascade → pagamento)
    assert sts[3].startswith("insert into core.ap005_ur")
    assert sts[4].startswith("insert into core.ap005_pagamento")


def test_fonte_multi_titular_sem_titular_id():
    fonte = loader.gerar_statements(_res(), nome_original="AP005.csv")[1]
    assert "'AP005'" in fonte
    # arquivo multi-titular: a linha de fonte_arquivo NÃO grava titular_id (fica nulo)
    assert "titular_id" not in fonte
    assert "'2026-06-05'::date" in fonte                            # data_referencia do nome


def test_dois_titulares_distintos_no_upsert():
    titular = loader.gerar_statements(_res(), nome_original="AP005.csv")[0]
    assert "('11111111000111')" in titular and "('33333333000133')" in titular
    assert titular.count("),") == 1                                 # exatamente 2 valores (1 vírgula entre eles)


def test_ur_resolve_titular_por_usuario_final():
    ur = loader.gerar_statements(_res(), nome_original="AP005.csv")[3]
    assert "join core.titular t on t.cnpj = d.usuario_final_doc" in ur
    assert "d.data_liquidacao::date" in ur and "d.atualizado_em::timestamptz" in ur


def test_pagamento_religa_a_ur_por_fonte_e_linha():
    pag = loader.gerar_statements(_res(), nome_original="AP005.csv")[4]
    assert "join core.ap005_ur u on u.fonte_id =" in pag and "u.linha = d.linha" in pag
    assert "'abc-123'" in pag                                       # identificador CERC do efeito de contrato
    assert "d.data_liquidacao_efetiva::date" in pag


def test_escape_de_aspas_simples():
    from dataclasses import replace
    res = _res()
    # injeta uma aspa simples na referência externa e confirma o escape (dobra)
    res.urs[0] = replace(res.urs[0], referencia_externa="D'OURO")
    ur = loader.gerar_statements(res, nome_original="x.csv")[3]
    assert "'D''OURO'" in ur


def test_sem_pagamentos_gera_quatro_statements():
    linha = 'ID;reg;cred;11111111000111;MCD;2026-06-01;t;1;0;0;0;"";CART;0;0;2026-05-29T00:00:00Z\n'
    res = ap005.parse(linha, original_filename="x.csv", fallback_date=date(2026, 5, 29))
    sts = loader.gerar_statements(res, nome_original="x.csv")
    assert len(sts) == 4 and not any("ap005_pagamento" in s for s in sts)


def test_sql_unico_concatena_com_ponto_e_virgula():
    sql = loader.gerar_sql(_res(), nome_original="AP005.csv")
    assert sql.count(";\n\n") == 4 and sql.rstrip().endswith(";")
