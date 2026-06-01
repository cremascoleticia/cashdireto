"""Runner de indicadores (Fase 2, fatia 2) — o "cozinheiro".

Pega os dados canônicos já carregados (core.*), roda as fórmulas (radar/raiox/ap005/ap013/
ap013b/ap013c + onerado próprio×terceiros) e grava os números prontos em core.indicador_snapshot,
cada um etiquetado por escopo: 'loja' (um estabelecimento/CNPJ) ou 'grupo' (raiz de CNPJ).

Segue o padrão dos loaders: a lógica é pura e testável (montar_snapshots / gerar_statements);
ler/escrever no banco é uma casca fina (ler_contexto / executar). A LLM/dashboard nunca calculam.

`contexto` (montado pelo runner a partir do banco, ou pelos testes) tem o formato:
    {
      "loja":  { "<cnpj>": {<dados do estabelecimento>}, ... },
      "grupo": { "<raiz>": {<dados agregados do grupo>}, ... },
      "parametros": { "<cnpj|raiz>": {"detentor_proprio": ["<cnpj>", ...]} },
    }
onde <dados> pode conter: agenda_ur, raiox_dossie (loja) / raiox_dossies (grupo),
ap005_ur, ap005_pagamento, ap013_ur, ap013_contrato, ap013b_contrato, ap013c.
"""
from __future__ import annotations

import json
from typing import Mapping, Sequence

from . import ap005, ap013, ap013b, ap013c, calculos, radar, raiox

ESCOPOS = ("loja", "grupo")


def _headline(resultado) -> float | None:
    """Número-síntese de um resultado de indicador, quando existir (senão None)."""
    if isinstance(resultado, bool):
        return None
    if isinstance(resultado, (int, float)):
        return float(resultado)
    if isinstance(resultado, tuple):                       # (valor, detalhe) — ex.: onerado_proprio
        return resultado[0]
    if isinstance(resultado, Mapping):
        for k in ("total", "valor_constituido"):
            v = resultado.get(k)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                return float(v)
    return None


def _detalhe(resultado):
    """Estrutura de apoio (jsonb) de um resultado de indicador."""
    if isinstance(resultado, tuple):
        return resultado[1]
    if isinstance(resultado, Mapping):
        return dict(resultado)
    return None


def _indicadores(escopo: str, dados: Mapping, detentor_proprio: Sequence[str] | None):
    """Lista (nome, resultado) dos indicadores aplicáveis aos dados deste escopo."""
    out: list[tuple[str, object]] = []

    if dados.get("agenda_ur"):
        out.append(("radar_recebiveis", radar.indicadores_radar(dados["agenda_ur"])))

    if escopo == "loja" and dados.get("raiox_dossie"):
        out.append(("raiox_estabelecimento", raiox.por_estabelecimento(dados["raiox_dossie"])))
    if escopo == "grupo" and dados.get("raiox_dossies"):
        out.append(("raiox_raiz", raiox.agregar_por_raiz(dados["raiox_dossies"])))

    ur5, pag5 = dados.get("ap005_ur"), dados.get("ap005_pagamento")
    if ur5:
        out += [
            ("ap005_constituido_por_usuario_final", ap005.constituido_por_usuario_final(ur5)),
            ("ap005_constituido_por_titular_ur", ap005.constituido_por_titular_ur(ur5)),
            ("ap005_livre_por_usuario_final", ap005.livre_por_usuario_final(ur5)),
            ("ap005_total_ur_por_usuario_final", ap005.total_ur_por_usuario_final(ur5)),
        ]
    if pag5:
        out += [
            ("ap005_efeito_por_ordem", ap005.constituido_efeito_por_ordem(pag5)),
            ("ap005_onerado_por_ordem_regra", ap005.onerado_por_ordem_e_regra(pag5)),
            ("ap005_onerado_por_tipo_regra", ap005.onerado_por_tipo_info_e_regra(pag5)),
            ("ap005_efeito_por_ordem_beneficiario", ap005.constituido_efeito_por_ordem_e_beneficiario(pag5)),
            ("ap005_efeito_por_beneficiario", ap005.constituido_efeito_por_beneficiario(pag5)),
            ("onerado_proprio", calculos.onerado_proprio(pag5, detentor_proprio)),
            ("onerado_terceiros", calculos.onerado_terceiros(pag5, detentor_proprio)),
        ]

    ur13, con13 = dados.get("ap013_ur"), dados.get("ap013_contrato")
    if ur13:
        out += [
            ("ap013_constituido_por_usuario_final", ap013.constituido_por_usuario_final(ur13)),
            ("ap013_constituido_por_uf_oneracao", ap013.constituido_por_usuario_final_e_oneracao(ur13)),
            ("ap013_onerado_por_usuario_final", ap013.onerado_por_usuario_final(ur13)),
            ("ap013_onerado_por_uf_oneracao", ap013.onerado_por_usuario_final_e_oneracao(ur13)),
            ("ap013_onerado_por_uf_mes_oneracao", ap013.onerado_por_usuario_final_data_oneracao(ur13)),
            ("ap013_constituido_por_uf_mes_oneracao", ap013.constituido_por_usuario_final_data_oneracao(ur13)),
        ]
    if con13:
        out.append(("ap013_valor_a_manter_proprio",
                    ap013.valor_a_manter_proprio_por_contratante_efeito(con13, detentor_proprio)))

    if dados.get("ap013b_contrato"):
        out.append(("ap013b_calculado_credenciadoras_proprio",
                    ap013b.calculado_credenciadoras_proprio_por_contratante_efeito(
                        dados["ap013b_contrato"], detentor_proprio)))

    if dados.get("ap013c"):
        out += [
            ("ap013c_total_constituido_efeitos_depois", ap013c.total_constituido_efeitos_depois(dados["ap013c"])),
            ("ap013c_total_suficiencia_depois", ap013c.total_suficiencia_depois(dados["ap013c"])),
        ]

    return out


def montar_snapshots(contexto: Mapping, data_referencia) -> list[dict]:
    """Pura: transforma o contexto em registros de snapshot (um por indicador × escopo × chave)."""
    params = contexto.get("parametros", {})
    snaps: list[dict] = []
    for escopo in ESCOPOS:
        for chave, dados in (contexto.get(escopo) or {}).items():
            dp = (params.get(chave) or {}).get("detentor_proprio")
            for nome, resultado in _indicadores(escopo, dados, dp):
                snaps.append({
                    "escopo": escopo,
                    "chave": chave,                        # cnpj (loja) ou raiz (grupo)
                    "indicador": nome,
                    "valor": _headline(resultado),
                    "detalhe": _detalhe(resultado),
                    "data_referencia": data_referencia,
                })
    return snaps


def _q(s) -> str:
    if s is None:
        return "NULL"
    return "'" + str(s).replace("'", "''") + "'"


def _num(v) -> str:
    return "NULL" if v is None else repr(float(v))


def _jsonb(detalhe) -> str:
    if detalhe is None:
        return "NULL"
    txt = json.dumps(detalhe, ensure_ascii=False, default=str)   # default=str cobre date/Decimal
    return _q(txt) + "::jsonb"


def gerar_statements(snaps: Sequence[Mapping], data_referencia) -> list[str]:
    """SQL idempotente: apaga os snapshots da data e regrava. Loja resolve titular_id pelo cnpj;
    grupo grava titular_id nulo + cnpj_raiz."""
    dref = _q(str(data_referencia))
    stmts = [f"delete from core.indicador_snapshot where data_referencia = {dref}::date"]
    for s in snaps:
        if s["escopo"] == "loja":
            titular = f"(select id from core.titular where cnpj = {_q(s['chave'])})"
            cnpj_raiz = "NULL"
        else:
            titular = "NULL"
            cnpj_raiz = _q(s["chave"])
        stmts.append(
            "insert into core.indicador_snapshot\n"
            "  (titular_id, escopo, cnpj_raiz, indicador, valor, data_referencia, detalhe)\n"
            f"values ({titular}, {_q(s['escopo'])}, {cnpj_raiz}, {_q(s['indicador'])}, "
            f"{_num(s['valor'])}, {dref}::date, {_jsonb(s['detalhe'])})"
        )
    return stmts


def executar(conn, contexto: Mapping, data_referencia) -> int:
    """Casca fina: monta os snapshots e executa a carga numa conexão psycopg. Devolve nº de linhas."""
    snaps = montar_snapshots(contexto, data_referencia)
    for stmt in gerar_statements(snaps, data_referencia):
        conn.execute(stmt)
    return len(snaps)
