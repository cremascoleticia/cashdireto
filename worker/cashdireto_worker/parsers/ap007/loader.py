"""Carga do AP007 (parser → core). Gera SQL idempotente e/ou executa via psycopg.

AP007 é MULTI-TITULAR (como AP005/RADAR): um arquivo abrange vários contratantes.
- core.titular: upsert por cnpj (= contratante_doc / col4), cru.
- core.fonte_arquivo: upsert por sha256 (tipo AP007, titular_id NULO — multi-titular).
- core.ap007_contrato: delete-and-reload por fonte_id (reprocessável a partir do bruto).
- core.ap007_parcela: religada a cada contrato por (fonte_id, linha). O delete do contrato
  cai em cascata na parcela (on delete cascade), então não há delete próprio.

Escrita exige privilégio que ignore RLS (service_role / conexão postgres); nunca a chave anon.
"""
from __future__ import annotations

from .parser import Ap007ParseResult


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


def _arr(items) -> str:
    """list[str] → ARRAY['a','b']::text[]; lista vazia → NULL."""
    if not items:
        return "NULL"
    return "array[" + ", ".join(_q(x) for x in items) + "]::text[]"


def gerar_statements(res: Ap007ParseResult, *, nome_original: str) -> list[str]:
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
        f"values ('AP007', {_q(sha)}, {_q(nome_original)}, {_q(dref)}::date, 'validado',\n"
        f"        jsonb_build_object('formato','csv','contratos',{len(res.contratos)},"
        f"'parcelas',{res.total_parcelas},'sha256',{_q(sha)}))\n"
        "on conflict (sha256) do update set status='validado', data_referencia=excluded.data_referencia"
    )

    # cascade: apagar contratos do fonte_id derruba as parcelas junto (on delete cascade).
    delete_stmt = f"delete from core.ap007_contrato where fonte_id = {fonte_sub}"

    c_rows = ",\n  ".join(
        "("
        f"{c.linha}, {_q(c.tipo_operacao)}, {_q(c.referencia_externa)}, {_q(c.identificador_contrato)}, "
        f"{_q(c.contratante_doc)}, {_q(c.repactuacao)}, {_arr(c.identificadores_contrato_anterior)}, "
        f"{_q(c.participante_doc)}, {_q(c.detentor_doc)}, {_q(c.tipo_efeito)}, {_num(c.saldo_devedor)}, "
        f"{_num(c.limite_operacao_garantida)}, {_num(c.valor_a_manter)}, {_date(c.data_assinatura)}, "
        f"{_date(c.data_vencimento)}, {_q(c.tipo_servico)}, {_q(c.modalidade_operacao)}, {_q(c.carteira)}, "
        f"{_q(c.tipo_avaliacao)}, {_num(c.taxa_juros)}, {_q(c.indexador)}, {_q(c.aceite_incondicional)}"
        ")"
        for c in res.contratos
    )
    contrato_stmt = (
        "insert into core.ap007_contrato\n"
        "  (titular_id, fonte_id, linha, tipo_operacao, referencia_externa, identificador_contrato,\n"
        "   contratante_doc, repactuacao, identificadores_contrato_anterior, participante_doc, detentor_doc,\n"
        "   tipo_efeito, saldo_devedor, limite_operacao_garantida, valor_a_manter, data_assinatura,\n"
        "   data_vencimento, tipo_servico, modalidade_operacao, carteira, tipo_avaliacao, taxa_juros,\n"
        "   indexador, aceite_incondicional)\n"
        "select t.id, f.id, d.linha, d.tipo_operacao, d.referencia_externa, d.identificador_contrato,\n"
        "       d.contratante_doc, d.repactuacao, d.identificadores_contrato_anterior, d.participante_doc,\n"
        "       d.detentor_doc, d.tipo_efeito, d.saldo_devedor, d.limite_operacao_garantida, d.valor_a_manter,\n"
        "       d.data_assinatura::date, d.data_vencimento::date, d.tipo_servico, d.modalidade_operacao,\n"
        "       d.carteira, d.tipo_avaliacao, d.taxa_juros, d.indexador, d.aceite_incondicional\n"
        "from (values\n  "
        + c_rows
        + "\n) as d(linha, tipo_operacao, referencia_externa, identificador_contrato, contratante_doc,\n"
        "        repactuacao, identificadores_contrato_anterior, participante_doc, detentor_doc, tipo_efeito,\n"
        "        saldo_devedor, limite_operacao_garantida, valor_a_manter, data_assinatura, data_vencimento,\n"
        "        tipo_servico, modalidade_operacao, carteira, tipo_avaliacao, taxa_juros, indexador,\n"
        "        aceite_incondicional)\n"
        "join core.titular t on t.cnpj = d.contratante_doc\n"
        f"cross join {fonte_sub} f"
    )

    stmts = [titular_stmt, fonte_stmt, delete_stmt, contrato_stmt]

    p_rows = ",\n  ".join(
        f"({c.linha}, {p.ordem}, {_date(p.data_parcela)}, {_num(p.valor_parcela)})"
        for c in res.contratos
        for p in c.parcelas
    )
    if p_rows:
        parcela_stmt = (
            "insert into core.ap007_parcela\n"
            "  (contrato_id, ordem, data_parcela, valor_parcela)\n"
            "select c.id, d.ordem, d.data_parcela::date, d.valor_parcela\n"
            "from (values\n  "
            + p_rows
            + "\n) as d(linha, ordem, data_parcela, valor_parcela)\n"
            f"join core.ap007_contrato c on c.fonte_id = {fonte_sub} and c.linha = d.linha"
        )
        stmts.append(parcela_stmt)

    return stmts


def gerar_sql(res: Ap007ParseResult, *, nome_original: str) -> str:
    """Script único (para inspeção/psql); a carga via psycopg usa gerar_statements()."""
    return ";\n\n".join(gerar_statements(res, nome_original=nome_original)) + ";\n"


def carregar(conn, res: Ap007ParseResult, *, nome_original: str) -> None:
    """Executa a carga numa conexão psycopg, um statement por vez (mesma transação)."""
    for stmt in gerar_statements(res, nome_original=nome_original):
        conn.execute(stmt)
