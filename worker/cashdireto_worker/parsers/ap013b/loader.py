"""Carga do AP013B (parser → core). Gera SQL idempotente e/ou executa via psycopg.

AP013B é MULTI-TITULAR (como AP007/AP013/RADAR): um arquivo abrange vários contratantes.
- core.titular: upsert por cnpj (= contratante_doc / col3), cru.
- core.fonte_arquivo: upsert por sha256 (tipo AP013B, titular_id NULO — multi-titular).
- core.ap013b_contrato: delete-and-reload por fonte_id (reprocessável a partir do bruto).
- core.ap013b_credenciadora: religada a cada contrato por (fonte_id, linha). O delete do contrato
  cai em cascata na credenciadora (on delete cascade), então não há delete próprio.

Escrita exige privilégio que ignore RLS (service_role / conexão postgres); nunca a chave anon.
"""
from __future__ import annotations

from .parser import Ap013bParseResult


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


def gerar_statements(res: Ap013bParseResult, *, nome_original: str) -> list[str]:
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
        f"values ('AP013B', {_q(sha)}, {_q(nome_original)}, {_q(dref)}::date, 'validado',\n"
        f"        jsonb_build_object('formato','csv','contratos',{len(res.contratos)},"
        f"'credenciadoras',{res.total_credenciadoras},'sha256',{_q(sha)}))\n"
        "on conflict (sha256) do update set status='validado', data_referencia=excluded.data_referencia"
    )

    # cascade: apagar contratos do fonte_id derruba as credenciadoras junto (on delete cascade).
    delete_stmt = f"delete from core.ap013b_contrato where fonte_id = {fonte_sub}"

    c_rows = ",\n  ".join(
        "("
        f"{c.linha}, {_q(c.referencia_externa)}, {_q(c.identificador_contrato)}, {_q(c.contratante_doc)}, "
        f"{_q(c.repactuacao)}, {_q(c.identificador_contrato_anterior)}, {_q(c.participante_doc)}, "
        f"{_q(c.detentor_doc)}, {_q(c.carteira)}, {_q(c.tipo_servico)}, {_q(c.tipo_efeito)}, "
        f"{_num(c.saldo_devedor)}, {_date(c.data_criacao)}, {_date(c.data_assinatura)}, "
        f"{_date(c.data_vencimento)}, {_date(c.data_ultima_atualizacao)}, {_num(c.indicador_sobrecolateralizacao)}"
        ")"
        for c in res.contratos
    )
    contrato_stmt = (
        "insert into core.ap013b_contrato\n"
        "  (titular_id, fonte_id, linha, referencia_externa, identificador_contrato, contratante_doc,\n"
        "   repactuacao, identificador_contrato_anterior, participante_doc, detentor_doc, carteira,\n"
        "   tipo_servico, tipo_efeito, saldo_devedor, data_criacao, data_assinatura, data_vencimento,\n"
        "   data_ultima_atualizacao, indicador_sobrecolateralizacao)\n"
        "select t.id, f.id, d.linha, d.referencia_externa, d.identificador_contrato, d.contratante_doc,\n"
        "       d.repactuacao, d.identificador_contrato_anterior, d.participante_doc, d.detentor_doc,\n"
        "       d.carteira, d.tipo_servico, d.tipo_efeito, d.saldo_devedor, d.data_criacao::date,\n"
        "       d.data_assinatura::date, d.data_vencimento::date, d.data_ultima_atualizacao::date,\n"
        "       d.indicador_sobrecolateralizacao\n"
        "from (values\n  "
        + c_rows
        + "\n) as d(linha, referencia_externa, identificador_contrato, contratante_doc, repactuacao,\n"
        "        identificador_contrato_anterior, participante_doc, detentor_doc, carteira, tipo_servico,\n"
        "        tipo_efeito, saldo_devedor, data_criacao, data_assinatura, data_vencimento,\n"
        "        data_ultima_atualizacao, indicador_sobrecolateralizacao)\n"
        "join core.titular t on t.cnpj = d.contratante_doc\n"
        f"cross join {fonte_sub} f"
    )

    stmts = [titular_stmt, fonte_stmt, delete_stmt, contrato_stmt]

    cred_rows = ",\n  ".join(
        "("
        f"{c.linha}, {cr.ordem}, {_q(cr.entidade_registradora_doc)}, {_q(cr.credenciadora_doc)}, "
        f"{_int(cr.qtd_ur_constituidas)}, {_int(cr.qtd_ur_nao_constituidas)}, {_int(cr.qtd_efeitos)}, "
        f"{_num(cr.valor_efeitos_solicitados)}, {_num(cr.valor_efeitos_calculados_cerc)}, "
        f"{_num(cr.valor_efeitos_calculados_credenciadoras)}, {_int(cr.qtd_ur_prioridade_1)}, "
        f"{_int(cr.qtd_ur_prioridade_diferente_1)}"
        ")"
        for c in res.contratos
        for cr in c.credenciadoras
    )
    if cred_rows:
        cred_stmt = (
            "insert into core.ap013b_credenciadora\n"
            "  (contrato_id, ordem, entidade_registradora_doc, credenciadora_doc, qtd_ur_constituidas,\n"
            "   qtd_ur_nao_constituidas, qtd_efeitos, valor_efeitos_solicitados, valor_efeitos_calculados_cerc,\n"
            "   valor_efeitos_calculados_credenciadoras, qtd_ur_prioridade_1, qtd_ur_prioridade_diferente_1)\n"
            "select c.id, d.ordem, d.entidade_registradora_doc, d.credenciadora_doc, d.qtd_ur_constituidas,\n"
            "       d.qtd_ur_nao_constituidas, d.qtd_efeitos, d.valor_efeitos_solicitados, d.valor_efeitos_calculados_cerc,\n"
            "       d.valor_efeitos_calculados_credenciadoras, d.qtd_ur_prioridade_1, d.qtd_ur_prioridade_diferente_1\n"
            "from (values\n  "
            + cred_rows
            + "\n) as d(linha, ordem, entidade_registradora_doc, credenciadora_doc, qtd_ur_constituidas,\n"
            "        qtd_ur_nao_constituidas, qtd_efeitos, valor_efeitos_solicitados, valor_efeitos_calculados_cerc,\n"
            "        valor_efeitos_calculados_credenciadoras, qtd_ur_prioridade_1, qtd_ur_prioridade_diferente_1)\n"
            f"join core.ap013b_contrato c on c.fonte_id = {fonte_sub} and c.linha = d.linha"
        )
        stmts.append(cred_stmt)

    return stmts


def gerar_sql(res: Ap013bParseResult, *, nome_original: str) -> str:
    """Script único (para inspeção/psql); a carga via psycopg usa gerar_statements()."""
    return ";\n\n".join(gerar_statements(res, nome_original=nome_original)) + ";\n"


def carregar(conn, res: Ap013bParseResult, *, nome_original: str) -> None:
    """Executa a carga numa conexão psycopg, um statement por vez (mesma transação)."""
    for stmt in gerar_statements(res, nome_original=nome_original):
        conn.execute(stmt)
