"""Carga do RAIOX (parser → core). Gera SQL idempotente e/ou executa via psycopg.

- core.titular: upsert por cnpj (preenche razão + cadastro).
- core.fonte_arquivo: upsert por sha256 (tipo RAIOX, single-titular → titular_id preenchido).
- raiox_indicador / raiox_serie_mensal / raiox_relacionamento: delete-and-reload por fonte_id.
"""
from __future__ import annotations

from .parser import RaioxParseResult


def _q(s) -> str:
    if s is None:
        return "NULL"
    return "'" + str(s).replace("'", "''") + "'"


def _num(v) -> str:
    return "NULL" if v is None else repr(float(v))


def gerar_statements(res: RaioxParseResult, *, nome_original: str) -> list[str]:
    cad = res.cadastro
    cnpj = cad["cnpj"]
    if not cnpj:
        from .parser import RaioxParseError
        raise RaioxParseError("RAIOX sem CNPJ no cadastro — não dá para resolver o titular")
    sha = res.sha256
    dref = res.data_referencia.isoformat()

    titular = (
        "insert into core.titular (cnpj, razao_social, natureza_juridica, setor_economico, situacao_cadastral)\n"
        f"values ({_q(cnpj)}, {_q(cad.get('razao_social'))}, {_q(cad.get('natureza_juridica'))}, "
        f"{_q(cad.get('setor_economico'))}, {_q(cad.get('situacao_cadastral'))})\n"
        "on conflict (cnpj) do update set "
        "razao_social=coalesce(excluded.razao_social, core.titular.razao_social), "
        "natureza_juridica=excluded.natureza_juridica, setor_economico=excluded.setor_economico, "
        "situacao_cadastral=excluded.situacao_cadastral"
    )

    fonte = (
        "insert into core.fonte_arquivo (titular_id, tipo, sha256, nome_original, data_referencia, status, payload_bruto)\n"
        f"select t.id, 'RAIOX', {_q(sha)}, {_q(nome_original)}, {_q(dref)}::date, 'validado',\n"
        f"       jsonb_build_object('formato','html','sha256',{_q(sha)})\n"
        f"from core.titular t where t.cnpj = {_q(cnpj)}\n"
        "on conflict (sha256) do update set status='validado', "
        "data_referencia=excluded.data_referencia, titular_id=excluded.titular_id"
    )

    def_del = lambda tabela: f"delete from core.{tabela} where fonte_id = (select id from core.fonte_arquivo where sha256={_q(sha)})"

    # CTE base: resolve titular_id (cnpj) e fonte_id (sha) para os inserts
    base_from = (
        f"cross join (select id from core.fonte_arquivo where sha256={_q(sha)}) f\n"
        f"join core.titular t on t.cnpj = {_q(cnpj)}"
    )

    ind_rows = ",\n  ".join(
        f"({_q(d['chave'])}, {_num(d['valor'])}, {_q(d['unidade'])}, {_q(d['texto_extra'])}, {_q(d['definicao'])})"
        for d in res.indicadores
    )
    indicadores = (
        "insert into core.raiox_indicador (titular_id, fonte_id, data_referencia, chave, valor, unidade, texto_extra, definicao)\n"
        f"select t.id, f.id, {_q(dref)}::date, d.chave, d.valor, d.unidade, d.texto_extra, d.definicao\n"
        f"from (values\n  {ind_rows}\n) as d(chave, valor, unidade, texto_extra, definicao)\n{base_from}"
    )

    serie_sql = ""
    if res.serie_mensal:
        s_rows = ",\n  ".join(
            f"({_q(s['competencia'].isoformat())}::date, {_q(s['serie'])}, {_num(s['valor'])})"
            for s in res.serie_mensal
        )
        serie_sql = (
            "insert into core.raiox_serie_mensal (titular_id, fonte_id, competencia, serie, valor)\n"
            f"select t.id, f.id, d.competencia, d.serie, d.valor\n"
            f"from (values\n  {s_rows}\n) as d(competencia, serie, valor)\n{base_from}"
        )

    rel_sql = ""
    if res.relacionamentos:
        r_rows = ",\n  ".join(
            f"({_q(x['tipo'])}, {_q(x['nome'])}, {_num(x['percentual'])})"
            for x in res.relacionamentos
        )
        rel_sql = (
            "insert into core.raiox_relacionamento (titular_id, fonte_id, tipo, nome, percentual)\n"
            f"select t.id, f.id, d.tipo, d.nome, d.percentual\n"
            f"from (values\n  {r_rows}\n) as d(tipo, nome, percentual)\n{base_from}"
        )

    stmts = [titular, fonte,
             def_del("raiox_indicador"), def_del("raiox_serie_mensal"), def_del("raiox_relacionamento"),
             indicadores]
    if serie_sql:
        stmts.append(serie_sql)
    if rel_sql:
        stmts.append(rel_sql)
    return stmts


def gerar_sql(res: RaioxParseResult, *, nome_original: str) -> str:
    return ";\n\n".join(gerar_statements(res, nome_original=nome_original)) + ";\n"


def carregar(conn, res: RaioxParseResult, *, nome_original: str) -> None:
    for stmt in gerar_statements(res, nome_original=nome_original):
        conn.execute(stmt)
