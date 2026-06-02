"""Monta o "contexto" que o runner consome — agrupa as linhas canônicas por loja e por grupo.

`montar_contexto` é pura/testável: recebe as linhas já lidas do banco (dict fonte → lista de
linhas) e devolve {"loja": {cnpj: {...}}, "grupo": {raiz: {...}}, "parametros": {...}} no formato
que `runner.montar_snapshots` espera. `ler_contexto` é a casca fina que lê de core.* via psycopg.

A chave da loja é o CNPJ normalizado (só dígitos); o grupo é a raiz (8 primeiros dígitos). Cada
fonte tem o campo que identifica a loja (estabelecimento/usuário final/contratante).
"""
from __future__ import annotations

from typing import Mapping, Sequence

# fonte (chave no contexto) → campo da linha que identifica a loja (CNPJ do estabelecimento)
FONTES_LOJA = (
    ("agenda_ur", "estabelecimento_cnpj"),
    ("ap005_ur", "usuario_final_doc"),
    ("ap005_pagamento", "usuario_final_doc"),     # anexado via join com ap005_ur
    ("ap013_ur", "usuario_final_doc"),
    ("ap013_contrato", "contratante_doc"),
    ("ap013b_contrato", "contratante_doc"),
    ("ap013c", "contratante_doc"),
)


def norm_cnpj(cnpj: str | None) -> str | None:
    """CNPJ só com dígitos (unifica formatado × cru entre fontes). None se vazio."""
    if not cnpj:
        return None
    digitos = "".join(c for c in cnpj if c.isdigit())
    return digitos or None


def raiz_cnpj(cnpj: str | None) -> str | None:
    d = norm_cnpj(cnpj)
    return d[:8] if d else None


def montar_contexto(dados: Mapping[str, Sequence[Mapping]],
                    raiox_dossies: Sequence[Mapping] | None = None,
                    parametros: Mapping | None = None) -> dict:
    """Agrupa as linhas por loja (CNPJ) e por grupo (raiz). Vide formato no topo do módulo."""
    ctx: dict = {"loja": {}, "grupo": {}, "parametros": dict(parametros or {})}

    def loja(cnpj: str) -> dict:
        return ctx["loja"].setdefault(cnpj, {})

    def grupo(r: str) -> dict:
        return ctx["grupo"].setdefault(r, {})

    for fonte, campo in FONTES_LOJA:
        for row in dados.get(fonte, []) or []:
            cnpj = norm_cnpj(row.get(campo))
            if not cnpj:
                continue
            loja(cnpj).setdefault(fonte, []).append(row)
            grupo(cnpj[:8]).setdefault(fonte, []).append(row)

    for d in raiox_dossies or []:
        cnpj = norm_cnpj(d.get("cnpj"))
        if not cnpj:
            continue
        loja(cnpj)["raiox_dossie"] = d                 # 1 dossiê por estabelecimento
        grupo(cnpj[:8]).setdefault("raiox_dossies", []).append(d)

    return ctx


# ───────────────────────── Leitura do banco (casca fina) ─────────────────────────

def _linhas(cur, sql: str) -> list[dict]:
    cur.execute(sql)
    cols = [c.name for c in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def ler_contexto(conn) -> dict:
    """Lê core.* e monta o contexto. Casca fina (não testada sem banco)."""
    with conn.cursor() as cur:
        dados = {
            "agenda_ur": _linhas(cur, "select estabelecimento_cnpj, credenciadora_doc, arranjo, "
                                      "janela, situacao, valor from core.agenda_ur"),
            "ap005_ur": _linhas(cur, "select usuario_final_doc, titular_ur_doc, data_liquidacao, "
                                     "valor_constituido_total, valor_livre, valor_total_ur from core.ap005_ur"),
            "ap005_pagamento": _linhas(cur,
                "select u.usuario_final_doc, p.indicador_ordem_efeito, p.tipo_informacao_pagamento, "
                "p.regra_divisao, p.valor_onerado, p.valor_constituido_efeito, p.beneficiario_doc "
                "from core.ap005_pagamento p join core.ap005_ur u on u.id = p.ur_id"),
            "ap013_ur": _linhas(cur, "select usuario_final_doc, data_liquidacao, indicador_oneracao, "
                                     "valor_constituido_total, valor_onerado from core.ap013_ur"),
            "ap013_contrato": _linhas(cur, "select contratante_doc, detentor_doc, tipo_efeito, "
                                           "valor_a_manter, data_vencimento from core.ap013_contrato"),
            "ap013b_contrato": _linhas(cur,
                "select c.contratante_doc, c.detentor_doc, c.tipo_efeito, "
                "coalesce(sum(cr.valor_efeitos_calculados_credenciadoras),0) as valor_efeitos_calculados_credenciadoras "
                "from core.ap013b_contrato c left join core.ap013b_credenciadora cr on cr.contrato_id = c.id "
                "group by c.id, c.contratante_doc, c.detentor_doc, c.tipo_efeito"),
            "ap013c": _linhas(cur, "select contratante_doc, valor_constituido_efeitos_depois, "
                                   "valor_suficiencia_depois from core.ap013c_redistribuicao"),
        }
        # RAIOX: monta um dossiê por titular (cnpj)
        ind = _linhas(cur, "select t.cnpj, i.chave, i.valor from core.raiox_indicador i "
                           "join core.titular t on t.id = i.titular_id")
        serie = _linhas(cur, "select t.cnpj, s.competencia, s.serie, s.valor from core.raiox_serie_mensal s "
                             "join core.titular t on t.id = s.titular_id")
        rel = _linhas(cur, "select t.cnpj, r.tipo, r.nome, r.percentual from core.raiox_relacionamento r "
                           "join core.titular t on t.id = r.titular_id")
        params = _linhas(cur, "select t.cnpj, p.detentor_proprio from core.parametro_titular p "
                              "join core.titular t on t.id = p.titular_id")

    dossies: dict[str, dict] = {}
    for r in ind:
        d = dossies.setdefault(r["cnpj"], {"cnpj": r["cnpj"], "indicadores": {}, "serie_mensal": [], "relacionamentos": []})
        d["indicadores"][r["chave"]] = r["valor"]
    for r in serie:
        dossies.setdefault(r["cnpj"], {"cnpj": r["cnpj"], "indicadores": {}, "serie_mensal": [], "relacionamentos": []})
        dossies[r["cnpj"]]["serie_mensal"].append({"competencia": r["competencia"], "serie": r["serie"], "valor": r["valor"]})
    for r in rel:
        dossies.setdefault(r["cnpj"], {"cnpj": r["cnpj"], "indicadores": {}, "serie_mensal": [], "relacionamentos": []})
        dossies[r["cnpj"]]["relacionamentos"].append({"tipo": r["tipo"], "nome": r["nome"], "percentual": r["percentual"]})

    parametros: dict = {}
    for r in params:
        cnpj = norm_cnpj(r["cnpj"])
        if cnpj and r["detentor_proprio"]:
            parametros[cnpj] = {"detentor_proprio": r["detentor_proprio"]}
            parametros[cnpj[:8]] = {"detentor_proprio": r["detentor_proprio"]}

    return montar_contexto(dados, raiox_dossies=list(dossies.values()), parametros=parametros)
