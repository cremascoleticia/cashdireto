"""Carga do AP005 (parser → core). Gera SQL idempotente e/ou executa via psycopg.

AP005 é MULTI-TITULAR (como o RADAR): um arquivo abrange vários usuários finais recebedores.
- core.titular: upsert por cnpj (= usuario_final_doc / col4), sem normalizar (cru, igual ao RADAR).
- core.fonte_arquivo: upsert por sha256 (tipo AP005, titular_id NULO — arquivo multi-titular).
- core.ap005_ur: delete-and-reload por fonte_id (reprocessável a partir do bruto).
- core.ap005_pagamento: religado a cada UR por (fonte_id, linha) — chave única da UR no arquivo.
  O delete da UR cai em cascata no pagamento (on delete cascade), então não há delete próprio.

Escrita exige privilégio que ignore RLS (service_role / conexão postgres); nunca a chave anon.
"""
from __future__ import annotations

from .parser import Ap005ParseResult


def _q(s) -> str:
    """Literal SQL string com aspas simples escapadas (NULL quando ausente)."""
    if s is None:
        return "NULL"
    return "'" + str(s).replace("'", "''") + "'"


def _num(v) -> str:
    return "NULL" if v is None else repr(float(v))


def _date(d) -> str:
    """date|None → literal 'AAAA-MM-DD' (o ::date fica no SELECT)."""
    return "NULL" if d is None else f"'{d.isoformat()}'"


def gerar_statements(res: Ap005ParseResult, *, nome_original: str) -> list[str]:
    """Statements de carga idempotente (um comando cada — seguro para psycopg3)."""
    sha = res.sha256
    dref = res.data_referencia.isoformat()
    fonte_sub = f"(select id from core.fonte_arquivo where sha256={_q(sha)})"

    titulares = ", ".join(f"({_q(c)})" for c in sorted(res.usuarios_finais))
    titular_stmt = (
        f"insert into core.titular (cnpj) values {titulares}\n"
        "on conflict (cnpj) do nothing"
    )

    fonte_stmt = (
        "insert into core.fonte_arquivo (tipo, sha256, nome_original, data_referencia, status, payload_bruto)\n"
        f"values ('AP005', {_q(sha)}, {_q(nome_original)}, {_q(dref)}::date, 'validado',\n"
        f"        jsonb_build_object('formato','csv','urs',{len(res.urs)},"
        f"'pagamentos',{res.total_pagamentos},'sha256',{_q(sha)}))\n"
        "on conflict (sha256) do update set status='validado', data_referencia=excluded.data_referencia"
    )

    # cascade: apagar URs do fonte_id derruba os pagamentos junto (on delete cascade).
    delete_stmt = f"delete from core.ap005_ur where fonte_id = {fonte_sub}"

    ur_rows = ",\n  ".join(
        "("
        f"{u.linha}, {_q(u.referencia_externa)}, {_q(u.registradora_doc)}, {_q(u.credenciadora_doc)}, "
        f"{_q(u.usuario_final_doc)}, {_q(u.arranjo)}, {_date(u.data_liquidacao)}, {_q(u.titular_ur_doc)}, "
        f"{_q(u.constituicao)}, {_num(u.valor_constituido_total)}, {_num(u.valor_constituido_antecip)}, "
        f"{_num(u.valor_bloqueado)}, {_q(u.carteira)}, {_num(u.valor_livre)}, {_num(u.valor_total_ur)}, "
        f"{_q(u.atualizado_em)}"
        ")"
        for u in res.urs
    )
    ur_stmt = (
        "insert into core.ap005_ur\n"
        "  (titular_id, fonte_id, linha, referencia_externa, registradora_doc, credenciadora_doc,\n"
        "   usuario_final_doc, arranjo, data_liquidacao, titular_ur_doc, constituicao,\n"
        "   valor_constituido_total, valor_constituido_antecip, valor_bloqueado, carteira,\n"
        "   valor_livre, valor_total_ur, atualizado_em)\n"
        "select t.id, f.id, d.linha, d.referencia_externa, d.registradora_doc, d.credenciadora_doc,\n"
        "       d.usuario_final_doc, d.arranjo, d.data_liquidacao::date, d.titular_ur_doc, d.constituicao,\n"
        "       d.valor_constituido_total, d.valor_constituido_antecip, d.valor_bloqueado, d.carteira,\n"
        "       d.valor_livre, d.valor_total_ur, d.atualizado_em::timestamptz\n"
        "from (values\n  "
        + ur_rows
        + "\n) as d(linha, referencia_externa, registradora_doc, credenciadora_doc, usuario_final_doc,\n"
        "        arranjo, data_liquidacao, titular_ur_doc, constituicao, valor_constituido_total,\n"
        "        valor_constituido_antecip, valor_bloqueado, carteira, valor_livre, valor_total_ur,\n"
        "        atualizado_em)\n"
        "join core.titular t on t.cnpj = d.usuario_final_doc\n"
        f"cross join {fonte_sub} f"
    )

    stmts = [titular_stmt, fonte_stmt, delete_stmt, ur_stmt]

    pag_rows = ",\n  ".join(
        "("
        f"{u.linha}, {p.ordem}, {_q(p.titular_domicilio_doc)}, {_q(p.tipo_conta)}, {_q(p.compe)}, "
        f"{_q(p.ispb)}, {_q(p.agencia)}, {_q(p.conta)}, {_num(p.valor_a_pagar)}, {_q(p.beneficiario_doc)}, "
        f"{_date(p.data_liquidacao_efetiva)}, {_num(p.valor_liquidacao_efetiva)}, {_q(p.regra_divisao)}, "
        f"{_num(p.valor_onerado)}, {_q(p.tipo_informacao_pagamento)}, {_q(p.indicador_ordem_efeito)}, "
        f"{_num(p.valor_constituido_efeito)}, {_q(p.identificador_cerc_contrato)}"
        ")"
        for u in res.urs
        for p in u.pagamentos
    )
    if pag_rows:
        pag_stmt = (
            "insert into core.ap005_pagamento\n"
            "  (ur_id, ordem, titular_domicilio_doc, tipo_conta, compe, ispb, agencia, conta,\n"
            "   valor_a_pagar, beneficiario_doc, data_liquidacao_efetiva, valor_liquidacao_efetiva,\n"
            "   regra_divisao, valor_onerado, tipo_informacao_pagamento, indicador_ordem_efeito,\n"
            "   valor_constituido_efeito, identificador_cerc_contrato)\n"
            "select u.id, d.ordem, d.titular_domicilio_doc, d.tipo_conta, d.compe, d.ispb, d.agencia, d.conta,\n"
            "       d.valor_a_pagar, d.beneficiario_doc, d.data_liquidacao_efetiva::date, d.valor_liquidacao_efetiva,\n"
            "       d.regra_divisao, d.valor_onerado, d.tipo_informacao_pagamento, d.indicador_ordem_efeito,\n"
            "       d.valor_constituido_efeito, d.identificador_cerc_contrato\n"
            "from (values\n  "
            + pag_rows
            + "\n) as d(linha, ordem, titular_domicilio_doc, tipo_conta, compe, ispb, agencia, conta,\n"
            "        valor_a_pagar, beneficiario_doc, data_liquidacao_efetiva, valor_liquidacao_efetiva,\n"
            "        regra_divisao, valor_onerado, tipo_informacao_pagamento, indicador_ordem_efeito,\n"
            "        valor_constituido_efeito, identificador_cerc_contrato)\n"
            f"join core.ap005_ur u on u.fonte_id = {fonte_sub} and u.linha = d.linha"
        )
        stmts.append(pag_stmt)

    return stmts


def gerar_sql(res: Ap005ParseResult, *, nome_original: str) -> str:
    """Script único (para inspeção/psql); a carga via psycopg usa gerar_statements()."""
    return ";\n\n".join(gerar_statements(res, nome_original=nome_original)) + ";\n"


def carregar(conn, res: Ap005ParseResult, *, nome_original: str) -> None:
    """Executa a carga numa conexão psycopg, um statement por vez (mesma transação)."""
    for stmt in gerar_statements(res, nome_original=nome_original):
        conn.execute(stmt)
