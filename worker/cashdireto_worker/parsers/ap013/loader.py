"""Carga do AP013 (legado) (parser → core). Gera SQL idempotente e/ou executa via psycopg.

AP013 é MULTI-TITULAR (como AP005/AP007/RADAR): um arquivo abrange vários contratantes.
- core.titular: upsert por cnpj (= contratante_doc / col3), cru.
- core.fonte_arquivo: upsert por sha256 (tipo AP013, titular_id NULO — multi-titular).
- core.ap013_contrato: delete-and-reload por fonte_id (reprocessável a partir do bruto).
- core.ap013_ur: religada a cada contrato por (fonte_id, linha). O delete do contrato cai em
  cascata na UR (on delete cascade), então não há delete próprio.

Escrita exige privilégio que ignore RLS (service_role / conexão postgres); nunca a chave anon.
"""
from __future__ import annotations

from .parser import Ap013ParseResult


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


def gerar_statements(res: Ap013ParseResult, *, nome_original: str) -> list[str]:
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
        f"values ('AP013', {_q(sha)}, {_q(nome_original)}, {_q(dref)}::date, 'validado',\n"
        f"        jsonb_build_object('formato','csv','contratos',{len(res.contratos)},"
        f"'urs',{res.total_urs},'sha256',{_q(sha)}))\n"
        "on conflict (sha256) do update set status='validado', data_referencia=excluded.data_referencia"
    )

    # cascade: apagar contratos do fonte_id derruba as URs junto (on delete cascade).
    delete_stmt = f"delete from core.ap013_contrato where fonte_id = {fonte_sub}"

    c_rows = ",\n  ".join(
        "("
        f"{c.linha}, {_q(c.referencia_externa)}, {_q(c.identificador_contrato)}, {_q(c.contratante_doc)}, "
        f"{_q(c.repactuacao)}, {_q(c.identificador_contrato_anterior)}, {_q(c.participante_doc)}, "
        f"{_q(c.detentor_doc)}, {_q(c.tipo_efeito)}, {_num(c.saldo_devedor)}, "
        f"{_num(c.limite_operacao_garantida)}, {_num(c.valor_a_manter)}, {_date(c.data_vencimento)}, "
        f"{_q(c.indicadores_consistencia_raw)}, {_num(c.qtd_ur_alcancadas)}, {_num(c.valor_ur_alcancadas)}, "
        f"{_q(c.resultado_distribuicao_onus)}"
        ")"
        for c in res.contratos
    )
    contrato_stmt = (
        "insert into core.ap013_contrato\n"
        "  (titular_id, fonte_id, linha, referencia_externa, identificador_contrato, contratante_doc,\n"
        "   repactuacao, identificador_contrato_anterior, participante_doc, detentor_doc, tipo_efeito,\n"
        "   saldo_devedor, limite_operacao_garantida, valor_a_manter, data_vencimento,\n"
        "   indicadores_consistencia_raw, qtd_ur_alcancadas, valor_ur_alcancadas, resultado_distribuicao_onus)\n"
        "select t.id, f.id, d.linha, d.referencia_externa, d.identificador_contrato, d.contratante_doc,\n"
        "       d.repactuacao, d.identificador_contrato_anterior, d.participante_doc, d.detentor_doc,\n"
        "       d.tipo_efeito, d.saldo_devedor, d.limite_operacao_garantida, d.valor_a_manter,\n"
        "       d.data_vencimento::date, d.indicadores_consistencia_raw, d.qtd_ur_alcancadas,\n"
        "       d.valor_ur_alcancadas, d.resultado_distribuicao_onus\n"
        "from (values\n  "
        + c_rows
        + "\n) as d(linha, referencia_externa, identificador_contrato, contratante_doc, repactuacao,\n"
        "        identificador_contrato_anterior, participante_doc, detentor_doc, tipo_efeito, saldo_devedor,\n"
        "        limite_operacao_garantida, valor_a_manter, data_vencimento, indicadores_consistencia_raw,\n"
        "        qtd_ur_alcancadas, valor_ur_alcancadas, resultado_distribuicao_onus)\n"
        "join core.titular t on t.cnpj = d.contratante_doc\n"
        f"cross join {fonte_sub} f"
    )

    stmts = [titular_stmt, fonte_stmt, delete_stmt, contrato_stmt]

    u_rows = ",\n  ".join(
        "("
        f"{c.linha}, {u.ordem}, {_q(u.entidade_registradora_doc)}, {_q(u.credenciadora_doc)}, "
        f"{_q(u.usuario_final_doc)}, {_q(u.arranjo)}, {_date(u.data_liquidacao)}, {_q(u.titular_ur_doc)}, "
        f"{_q(u.constituicao)}, {_num(u.valor_constituido_total)}, {_num(u.valor_bloqueado)}, "
        f"{_q(u.indicador_oneracao)}, {_q(u.regra_divisao)}, {_num(u.valor_onerado)}, "
        f"{_q(u.referencia_externa)}, {_num(u.valor_constituido_efeito)}"
        ")"
        for c in res.contratos
        for u in c.urs
    )
    if u_rows:
        ur_stmt = (
            "insert into core.ap013_ur\n"
            "  (contrato_id, ordem, entidade_registradora_doc, credenciadora_doc, usuario_final_doc,\n"
            "   arranjo, data_liquidacao, titular_ur_doc, constituicao, valor_constituido_total,\n"
            "   valor_bloqueado, indicador_oneracao, regra_divisao, valor_onerado, referencia_externa,\n"
            "   valor_constituido_efeito)\n"
            "select c.id, d.ordem, d.entidade_registradora_doc, d.credenciadora_doc, d.usuario_final_doc,\n"
            "       d.arranjo, d.data_liquidacao::date, d.titular_ur_doc, d.constituicao, d.valor_constituido_total,\n"
            "       d.valor_bloqueado, d.indicador_oneracao, d.regra_divisao, d.valor_onerado, d.referencia_externa,\n"
            "       d.valor_constituido_efeito\n"
            "from (values\n  "
            + u_rows
            + "\n) as d(linha, ordem, entidade_registradora_doc, credenciadora_doc, usuario_final_doc,\n"
            "        arranjo, data_liquidacao, titular_ur_doc, constituicao, valor_constituido_total,\n"
            "        valor_bloqueado, indicador_oneracao, regra_divisao, valor_onerado, referencia_externa,\n"
            "        valor_constituido_efeito)\n"
            f"join core.ap013_contrato c on c.fonte_id = {fonte_sub} and c.linha = d.linha"
        )
        stmts.append(ur_stmt)

    return stmts


def gerar_sql(res: Ap013ParseResult, *, nome_original: str) -> str:
    """Script único (para inspeção/psql); a carga via psycopg usa gerar_statements()."""
    return ";\n\n".join(gerar_statements(res, nome_original=nome_original)) + ";\n"


def carregar(conn, res: Ap013ParseResult, *, nome_original: str) -> None:
    """Executa a carga numa conexão psycopg, um statement por vez (mesma transação)."""
    for stmt in gerar_statements(res, nome_original=nome_original):
        conn.execute(stmt)
