"""Indicadores da fonte AP013B (Fase 2) — efeitos calculados por credenciadora.

Função pura (sem banco). Definição da área (2026-06-01): por contratante, **para o detentor =
ao CNPJ próprio** (parâmetro), por tipo de efeito, o Valor total dos efeitos calculados pelas
Credenciadoras **no contrato**.

Entrada: linhas de contrato já com o total do contrato somado das credenciadoras —
`valor_efeitos_calculados_credenciadoras` = Σ das linhas de core.ap013b_credenciadora daquele
contrato (o runner faz esse pré-agregado por contrato_id). Demais campos vêm de core.ap013b_contrato.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Mapping, Sequence


def calculado_credenciadoras_proprio_por_contratante_efeito(
    contrato_rows: Sequence[Mapping], detentor_proprio: Sequence[str] | None
) -> dict:
    """Filtra contratos do detentor próprio; agrupa por contratante e tipo de efeito, somando o
    valor total dos efeitos calculados pelas credenciadoras no contrato. Sem parâmetro → indisponível."""
    if not detentor_proprio:
        return {"total": None, "grupos": [], "motivo": "parametro detentor_proprio não definido"}
    proprios = set(detentor_proprio)
    acc: dict[tuple, float] = defaultdict(float)
    grand = 0.0
    for r in contrato_rows:
        if r.get("detentor_doc") not in proprios:
            continue
        v = r.get("valor_efeitos_calculados_credenciadoras")
        if v is None:
            continue
        acc[(r.get("contratante_doc"), r.get("tipo_efeito"))] += v
        grand += v
    grupos = [
        {"contratante_doc": c, "tipo_efeito": t, "valor": val}
        for (c, t), val in acc.items()
    ]
    grupos.sort(key=lambda g: g["valor"], reverse=True)
    return {"total": grand, "grupos": grupos}
