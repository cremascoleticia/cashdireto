"""Indicadores da fonte AP013 (legado) (Fase 2) — situação dos contratos + URs alcançadas.

Funções puras (sem banco). Definições fornecidas pela área (2026-06-01). Como nas demais fontes,
a mesma função serve por estabelecimento e por raiz de CNPJ (muda só quais linhas entram).

Nível UR (core.ap013_ur: usuario_final_doc, data_liquidacao, indicador_oneracao,
valor_constituido_total, valor_onerado): somas por usuário final, por indicador de oneração e/ou
por ano-mês da data de liquidação.

Nível contrato (core.ap013_contrato: contratante_doc, detentor_doc, tipo_efeito, valor_a_manter,
data_vencimento): visão filtrada ao detentor próprio (parâmetro), por contratante e tipo de efeito.

"por data de liquidação" é interpretado como ano-mês (AAAA-MM), como no AP005.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Callable, Mapping, Sequence


def _ym(d) -> str | None:
    return f"{d.year:04d}-{d.month:02d}" if d is not None else None


def _agrupar(rows: Sequence[Mapping], dims: list[tuple[str, Callable]], valor: str) -> dict:
    """Soma `valor` agrupando pelas dimensões (nome, extrator); lista de grupos + total geral."""
    acc: dict[tuple, float] = defaultdict(float)
    grand = 0.0
    for r in rows:
        v = r.get(valor)
        if v is None:
            continue
        acc[tuple(fn(r) for _, fn in dims)] += v
        grand += v
    grupos = [
        {**{nome: chave[i] for i, (nome, _) in enumerate(dims)}, "valor": val}
        for chave, val in acc.items()
    ]
    grupos.sort(key=lambda g: g["valor"], reverse=True)
    return {"total": grand, "grupos": grupos}


_UF = ("usuario_final_doc", lambda r: r.get("usuario_final_doc"))
_ONERACAO = ("indicador_oneracao", lambda r: r.get("indicador_oneracao"))
_MES = ("ano_mes", lambda r: _ym(r.get("data_liquidacao")))


# ───────────────────────── Nível UR ─────────────────────────

def constituido_por_usuario_final(ur_rows: Sequence[Mapping]) -> dict:
    """Σ valor constituído total por usuário final recebedor."""
    return _agrupar(ur_rows, [_UF], "valor_constituido_total")


def constituido_por_usuario_final_e_oneracao(ur_rows: Sequence[Mapping]) -> dict:
    """Σ valor constituído total por usuário final e indicador de oneração."""
    return _agrupar(ur_rows, [_UF, _ONERACAO], "valor_constituido_total")


def onerado_por_usuario_final(ur_rows: Sequence[Mapping]) -> dict:
    """Σ valor onerado na UR por usuário final recebedor."""
    return _agrupar(ur_rows, [_UF], "valor_onerado")


def onerado_por_usuario_final_e_oneracao(ur_rows: Sequence[Mapping]) -> dict:
    """Σ valor onerado por usuário final e indicador de oneração."""
    return _agrupar(ur_rows, [_UF, _ONERACAO], "valor_onerado")


def onerado_por_usuario_final_data_oneracao(ur_rows: Sequence[Mapping]) -> dict:
    """Σ valor onerado por usuário final, ano-mês da liquidação e indicador de oneração."""
    return _agrupar(ur_rows, [_UF, _MES, _ONERACAO], "valor_onerado")


def constituido_por_usuario_final_data_oneracao(ur_rows: Sequence[Mapping]) -> dict:
    """Σ valor constituído total por usuário final, ano-mês da liquidação e indicador de oneração."""
    return _agrupar(ur_rows, [_UF, _MES, _ONERACAO], "valor_constituido_total")


# ───────────────────────── Nível contrato (filtrado ao detentor próprio) ─────────────────────────

def valor_a_manter_proprio_por_contratante_efeito(
    contrato_rows: Sequence[Mapping], detentor_proprio: Sequence[str] | None
) -> dict:
    """Filtra contratos do detentor próprio; agrupa por contratante e tipo de efeito, somando
    valor a ser mantido e listando as datas de vencimento. Sem o parâmetro → indisponível."""
    if not detentor_proprio:
        return {"total": None, "grupos": [], "motivo": "parametro detentor_proprio não definido"}
    proprios = set(detentor_proprio)
    acc: dict[tuple, dict] = defaultdict(lambda: {"valor_a_manter": 0.0, "vencimentos": set()})
    grand = 0.0
    for r in contrato_rows:
        if r.get("detentor_doc") not in proprios:
            continue
        v = r.get("valor_a_manter") or 0.0
        g = acc[(r.get("contratante_doc"), r.get("tipo_efeito"))]
        g["valor_a_manter"] += v
        if r.get("data_vencimento") is not None:
            g["vencimentos"].add(r["data_vencimento"])
        grand += v
    grupos = [
        {"contratante_doc": c, "tipo_efeito": t, "valor_a_manter": g["valor_a_manter"],
         "data_vencimento": sorted(d.isoformat() for d in g["vencimentos"])}
        for (c, t), g in acc.items()
    ]
    grupos.sort(key=lambda x: x["valor_a_manter"], reverse=True)
    return {"total": grand, "grupos": grupos}
