"""Carga do RADAR (parser → core). Gera um SQL idempotente e/ou executa via psycopg.

Idempotência:
- `core.titular`  — upsert por `cnpj` (alias gerado pela sequence).
- `core.fonte_arquivo` — upsert por `sha256` (reenviar o mesmo arquivo não duplica).
- `core.agenda_ur` — apaga as linhas do `fonte_id` e regrava (reprocessável a partir do bruto).

Escrita exige privilégio que ignore RLS (service_role / conexão postgres); nunca a chave anon.
"""
from __future__ import annotations

from .parser import RadarParseResult


def _q(s: str) -> str:
    """Literal SQL string com aspas simples escapadas."""
    return "'" + s.replace("'", "''") + "'"


def gerar_statements(res: RadarParseResult, *, nome_original: str) -> list[str]:
    """Statements de carga idempotente (um comando cada — seguro para psycopg3)."""
    estabs = sorted(res.estabelecimentos)
    sha = res.sha256
    dref = res.data_referencia.isoformat()

    titulares = ", ".join(f"({_q(e)})" for e in estabs)

    linhas = []
    for r in res.registros:
        nome = _q(r.credenciadora_nome) if r.credenciadora_nome else "NULL"
        linhas.append(
            f"({_q(r.estabelecimento_cnpj)}, {_q(r.credenciadora_doc)}, {nome}, "
            f"{_q(r.arranjo)}, {_q(r.janela)}, {_q(r.situacao)}, {r.valor})"
        )
    values = ",\n  ".join(linhas)

    titular_stmt = (
        f"insert into core.titular (cnpj) values {titulares}\n"
        f"on conflict (cnpj) do nothing"
    )
    fonte_stmt = (
        "insert into core.fonte_arquivo (tipo, sha256, nome_original, data_referencia, status, payload_bruto)\n"
        f"values ('RADAR', {_q(sha)}, {_q(nome_original)}, {_q(dref)}::date, 'validado',\n"
        f"        jsonb_build_object('formato','csv','linhas_origem',{res.linhas_origem},'sha256',{_q(sha)}))\n"
        "on conflict (sha256) do update set status='validado', data_referencia=excluded.data_referencia"
    )
    delete_stmt = (
        "delete from core.agenda_ur\n"
        f"where fonte_id = (select id from core.fonte_arquivo where sha256={_q(sha)})"
    )
    agenda_stmt = (
        "insert into core.agenda_ur\n"
        "  (titular_id, fonte_id, data_referencia, estabelecimento_cnpj,\n"
        "   credenciadora_doc, credenciadora_nome, arranjo, janela, situacao, valor)\n"
        f"select t.id, f.id, {_q(dref)}::date, d.estab,\n"
        "       d.cred_doc, d.cred_nome, d.arranjo, d.janela, d.situacao, d.valor\n"
        f"from (values\n  {values}\n) as d(estab, cred_doc, cred_nome, arranjo, janela, situacao, valor)\n"
        "join core.titular t on t.cnpj = d.estab\n"
        f"cross join (select id from core.fonte_arquivo where sha256={_q(sha)}) f"
    )
    return [titular_stmt, fonte_stmt, delete_stmt, agenda_stmt]


def gerar_sql(res: RadarParseResult, *, nome_original: str) -> str:
    """Script único (para inspeção/psql); a carga via psycopg usa gerar_statements()."""
    return ";\n\n".join(gerar_statements(res, nome_original=nome_original)) + ";\n"


def carregar(conn, res: RadarParseResult, *, nome_original: str) -> None:
    """Executa a carga numa conexão psycopg, um statement por vez (mesma transação)."""
    for stmt in gerar_statements(res, nome_original=nome_original):
        conn.execute(stmt)
