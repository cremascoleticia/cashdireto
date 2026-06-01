"""Indicadores da fonte AP013C (Fase 2) — redistribuição do Gestão de Colateral.

Funções puras (sem banco). Definição da área (2026-06-01): somas totais pós-redistribuição.
Operam sobre linhas de core.ap013c_redistribuicao (a mesma função serve por estabelecimento e
por raiz — muda só quais linhas entram).
"""
from __future__ import annotations

from typing import Mapping, Sequence


def total_constituido_efeitos_depois(rows: Sequence[Mapping]) -> float:
    """Σ valor constituído dos efeitos depois da redistribuição."""
    return sum(r["valor_constituido_efeitos_depois"] for r in rows
               if r.get("valor_constituido_efeitos_depois") is not None)


def total_suficiencia_depois(rows: Sequence[Mapping]) -> float:
    """Σ valor em suficiência depois da redistribuição (<0 = déficit; >0 = excesso)."""
    return sum(r["valor_suficiencia_depois"] for r in rows
               if r.get("valor_suficiencia_depois") is not None)
