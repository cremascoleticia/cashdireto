"""Carga do AP013C (parser → core). Gera SQL idempotente e/ou executa via psycopg.

AP013C é MULTI-TITULAR (como AP007/AP013/AP013B): um arquivo abrange vários contratantes.
- core.titular: upsert por cnpj (= contratante_doc / col3), cru.
- core.fonte_arquivo: upsert por sha256 (tipo AP013C, titular_id NULO — multi-titular).
- core.ap013c_redistribuicao: delete-and-reload por fonte_id (reprocessável). Sem tabela filha.

Escrita exige privilégio que ignore RLS (service_role / conexão postgres); nunca a chave anon.
"""
from __future__ import annotations

from .parser import Ap013cParseResult


def _q(s) -> str:
    """Literal SQL string com aspas simples escapadas (NULL quando ausente)."""
    if s is None:
        return "NULL"
    return "'" + str(s).replace("'", "''") + "'"


def _num(v) -> str:
    return "NULL" if v is None else repr(float(v))


def _int(v) -> str:
    return "NULL" if v is None else str(int(v))


def _date(d) -> str:
    """date|None → literal 'AAAA-MM-DD' (o ::date fica no SELECT)."""
    return "NULL" if d is None else f"'{d.isoformat()}'"


def gerar_statements(res: Ap013cParseResult, *, nome_original: str) -> list[str]:
    """Statements de carga idempotente (um comando cada — seguro para psycopg3)."""
    sha = res.sha256
    dref = res.data_referencia.isoformat()
    fonte_sub = f"(select id from core.fonte_arquivo where sha256={_q(sha)})"

    titulares = ", ".join(f"({_q(c)})" for c in sorted(res.contratantes))
    titular_stmt = (
        f"insert into core.titular (cnpj) values {titulares}\n"
        "on conflict (cnpj) do nothing"
    )

    fonte_stmt = (
        "insert into core.fonte_arquivo (tipo, sha256, nome_original, data_referencia, status, payload_bruto)\n"
        f"values ('AP013C', {_q(sha)}, {_q(nome_original)}, {_q(dref)}::date, 'validado',\n"
        f"        jsonb_build_object('formato','csv','registros',{len(res.registros)},'sha256',{_q(sha)}))\n"
        "on conflict (sha256) do update set status='validado', data_referencia=excluded.data_referencia"
    )

    delete_stmt = f"delete from core.ap013c_redistribuicao where fonte_id = {fonte_sub}"

    rows = ",\n  ".join(
        "("
        f"{r.linha}, {_date(r.data_redistribuicao)}, {_q(r.referencia_externa)}, {_q(r.contratante_doc)}, "
        f"{_q(r.participante_doc)}, {_q(r.carteira)}, {_num(r.valor_minimo_a_manter)}, "
        f"{_num(r.valor_suficiencia_antes)}, {_int(r.qtd_ur_constituidas_antes)}, "
        f"{_int(r.qtd_ur_a_constituir_antes)}, {_num(r.valor_constituido_efeitos_antes)}, "
        f"{_num(r.valor_livre_agenda_antes)}, {_int(r.qtd_ur_constituidas_solicitadas)}, "
        f"{_int(r.qtd_ur_a_constituir_solicitadas)}, {_num(r.valor_suficiencia_depois)}, "
        f"{_int(r.qtd_ur_constituidas_depois)}, {_int(r.qtd_ur_a_constituir_depois)}, "
        f"{_num(r.valor_constituido_efeitos_depois)}, {_num(r.valor_agenda_anomala)}, {_q(r.observacoes)}"
        ")"
        for r in res.registros
    )
    registro_stmt = (
        "insert into core.ap013c_redistribuicao\n"
        "  (titular_id, fonte_id, linha, data_redistribuicao, referencia_externa, contratante_doc,\n"
        "   participante_doc, carteira, valor_minimo_a_manter, valor_suficiencia_antes,\n"
        "   qtd_ur_constituidas_antes, qtd_ur_a_constituir_antes, valor_constituido_efeitos_antes,\n"
        "   valor_livre_agenda_antes, qtd_ur_constituidas_solicitadas, qtd_ur_a_constituir_solicitadas,\n"
        "   valor_suficiencia_depois, qtd_ur_constituidas_depois, qtd_ur_a_constituir_depois,\n"
        "   valor_constituido_efeitos_depois, valor_agenda_anomala, observacoes)\n"
        "select t.id, f.id, d.linha, d.data_redistribuicao::date, d.referencia_externa, d.contratante_doc,\n"
        "       d.participante_doc, d.carteira, d.valor_minimo_a_manter, d.valor_suficiencia_antes,\n"
        "       d.qtd_ur_constituidas_antes, d.qtd_ur_a_constituir_antes, d.valor_constituido_efeitos_antes,\n"
        "       d.valor_livre_agenda_antes, d.qtd_ur_constituidas_solicitadas, d.qtd_ur_a_constituir_solicitadas,\n"
        "       d.valor_suficiencia_depois, d.qtd_ur_constituidas_depois, d.qtd_ur_a_constituir_depois,\n"
        "       d.valor_constituido_efeitos_depois, d.valor_agenda_anomala, d.observacoes\n"
        "from (values\n  "
        + rows
        + "\n) as d(linha, data_redistribuicao, referencia_externa, contratante_doc, participante_doc,\n"
        "        carteira, valor_minimo_a_manter, valor_suficiencia_antes, qtd_ur_constituidas_antes,\n"
        "        qtd_ur_a_constituir_antes, valor_constituido_efeitos_antes, valor_livre_agenda_antes,\n"
        "        qtd_ur_constituidas_solicitadas, qtd_ur_a_constituir_solicitadas, valor_suficiencia_depois,\n"
        "        qtd_ur_constituidas_depois, qtd_ur_a_constituir_depois, valor_constituido_efeitos_depois,\n"
        "        valor_agenda_anomala, observacoes)\n"
        "join core.titular t on t.cnpj = d.contratante_doc\n"
        f"cross join {fonte_sub} f"
    )

    return [titular_stmt, fonte_stmt, delete_stmt, registro_stmt]


def gerar_sql(res: Ap013cParseResult, *, nome_original: str) -> str:
    """Script único (para inspeção/psql); a carga via psycopg usa gerar_statements()."""
    return ";\n\n".join(gerar_statements(res, nome_original=nome_original)) + ";\n"


def carregar(conn, res: Ap013cParseResult, *, nome_original: str) -> None:
    """Executa a carga numa conexão psycopg, um statement por vez (mesma transação)."""
    for stmt in gerar_statements(res, nome_original=nome_original):
        conn.execute(stmt)
