"""Carga do AP013A (parser → core). Gera SQL idempotente e/ou executa via psycopg.

AP013A NÃO tem titular/contratante — é resumo agregado por Detentor. Por isso o loader
NÃO toca em core.titular: só grava core.fonte_arquivo (titular_id NULO) + as linhas do resumo.
- core.fonte_arquivo: upsert por sha256 (tipo AP013A).
- core.ap013a_resumo: delete-and-reload por fonte_id (reprocessável a partir do bruto).

Escrita exige privilégio que ignore RLS (service_role / conexão postgres); nunca a chave anon.
"""
from __future__ import annotations

from .parser import Ap013aParseResult


def _q(s) -> str:
    """Literal SQL string com aspas simples escapadas (NULL quando ausente)."""
    if s is None:
        return "NULL"
    return "'" + str(s).replace("'", "''") + "'"


def _num(v) -> str:
    return "NULL" if v is None else repr(float(v))


def _int(v) -> str:
    return "NULL" if v is None else str(int(v))


def gerar_statements(res: Ap013aParseResult, *, nome_original: str) -> list[str]:
    """Statements de carga idempotente (um comando cada — seguro para psycopg3)."""
    sha = res.sha256
    dref = res.data_referencia.isoformat()
    fonte_sub = f"(select id from core.fonte_arquivo where sha256={_q(sha)})"

    fonte_stmt = (
        "insert into core.fonte_arquivo (tipo, sha256, nome_original, data_referencia, status, payload_bruto)\n"
        f"values ('AP013A', {_q(sha)}, {_q(nome_original)}, {_q(dref)}::date, 'validado',\n"
        f"        jsonb_build_object('formato','csv','detentores',{len(res.resumos)},'sha256',{_q(sha)}))\n"
        "on conflict (sha256) do update set status='validado', data_referencia=excluded.data_referencia"
    )

    delete_stmt = f"delete from core.ap013a_resumo where fonte_id = {fonte_sub}"

    rows = ",\n  ".join(
        "("
        f"{r.linha}, {_q(r.detentor_doc)}, {_int(r.qtd_contratos)}, {_int(r.qtd_contratantes)}, "
        f"{_num(r.valor_saldo_devedor_total)}, {_int(r.qtd_ur_constituidas)}, {_int(r.qtd_ur_nao_constituidas)}, "
        f"{_int(r.qtd_efeitos)}, {_num(r.valor_efeitos_solicitados)}, {_num(r.valor_efeitos_calculados_cerc)}, "
        f"{_num(r.valor_efeitos_calculados_credenciadoras)}"
        ")"
        for r in res.resumos
    )
    resumo_stmt = (
        "insert into core.ap013a_resumo\n"
        "  (fonte_id, linha, detentor_doc, qtd_contratos, qtd_contratantes, valor_saldo_devedor_total,\n"
        "   qtd_ur_constituidas, qtd_ur_nao_constituidas, qtd_efeitos, valor_efeitos_solicitados,\n"
        "   valor_efeitos_calculados_cerc, valor_efeitos_calculados_credenciadoras)\n"
        "select f.id, d.linha, d.detentor_doc, d.qtd_contratos, d.qtd_contratantes, d.valor_saldo_devedor_total,\n"
        "       d.qtd_ur_constituidas, d.qtd_ur_nao_constituidas, d.qtd_efeitos, d.valor_efeitos_solicitados,\n"
        "       d.valor_efeitos_calculados_cerc, d.valor_efeitos_calculados_credenciadoras\n"
        "from (values\n  "
        + rows
        + "\n) as d(linha, detentor_doc, qtd_contratos, qtd_contratantes, valor_saldo_devedor_total,\n"
        "        qtd_ur_constituidas, qtd_ur_nao_constituidas, qtd_efeitos, valor_efeitos_solicitados,\n"
        "        valor_efeitos_calculados_cerc, valor_efeitos_calculados_credenciadoras)\n"
        f"cross join {fonte_sub} f"
    )

    return [fonte_stmt, delete_stmt, resumo_stmt]


def gerar_sql(res: Ap013aParseResult, *, nome_original: str) -> str:
    """Script único (para inspeção/psql); a carga via psycopg usa gerar_statements()."""
    return ";\n\n".join(gerar_statements(res, nome_original=nome_original)) + ";\n"


def carregar(conn, res: Ap013aParseResult, *, nome_original: str) -> None:
    """Executa a carga numa conexão psycopg, um statement por vez (mesma transação)."""
    for stmt in gerar_statements(res, nome_original=nome_original):
        conn.execute(stmt)
