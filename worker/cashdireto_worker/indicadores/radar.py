"""Indicadores da fonte RADAR (Fase 2) — recebíveis por situação, janela e arranjo.

Funções puras (sem banco). Definições fornecidas pela área (2026-06-01).

Diferente do RAIOX, os indicadores RADAR são calculados **da mesma forma** por estabelecimento
e por raiz de CNPJ — a diferença é apenas QUAIS linhas entram (um CNPJ vs. todos os
estabelecimentos do grupo). Logo, `indicadores_radar(rows)` serve aos dois níveis: o runner
passa as linhas filtradas pelo estabelecimento OU por todos os estabelecimentos da raiz.

Indicadores (sobre core.agenda_ur, situações livre/comprometido/constituido por janela e arranjo):
- valor_livre / valor_comprometido / valor_constituido (totais)
- nivel_comprometimento = comprometido / constituido
- por_janela: livre/comprometido/constituido + nível por janela de tempo
- por_arranjo: constituído por arranjo, com o percentual do arranjo frente ao total constituído

Formato de entrada (linha de core.agenda_ur):
    {"situacao": "livre"|"comprometido"|"constituido"|"pre", "janela": "0_30"|...,
     "arranjo": "MCC", "valor": 123.45, "estabelecimento_cnpj": "...", "credenciadora_doc": "..."}
"""
from __future__ import annotations

from collections import defaultdict
from typing import Mapping, Sequence


def _nivel(comprometido: float, constituido: float) -> float | None:
    """comprometido / constituido; None quando não há constituído (não estima)."""
    return (comprometido / constituido) if constituido else None


def indicadores_radar(rows: Sequence[Mapping]) -> dict:
    """Calcula os indicadores RADAR sobre um conjunto de linhas de agenda_ur (1 nível)."""
    total: dict[str, float] = defaultdict(float)               # por situação
    por_janela: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    por_arranjo: dict[str, float] = defaultdict(float)          # constituído por arranjo

    for r in rows:
        valor = r.get("valor")
        if valor is None:
            continue
        situacao = r.get("situacao")
        total[situacao] += valor
        if r.get("janela"):
            por_janela[r["janela"]][situacao] += valor
        if situacao == "constituido" and r.get("arranjo"):
            por_arranjo[r["arranjo"]] += valor

    livre = total.get("livre", 0.0)
    comprometido = total.get("comprometido", 0.0)
    constituido = total.get("constituido", 0.0)

    janelas = {}
    for jan, s in por_janela.items():
        c_comp, c_const = s.get("comprometido", 0.0), s.get("constituido", 0.0)
        janelas[jan] = {
            "livre": s.get("livre", 0.0),
            "comprometido": c_comp,
            "constituido": c_const,
            "nivel_comprometimento": _nivel(c_comp, c_const),
        }

    arranjos = [
        {"arranjo": arr, "valor_constituido": val,
         "percentual": (val / constituido) if constituido else None}
        for arr, val in sorted(por_arranjo.items(), key=lambda kv: kv[1], reverse=True)
    ]

    return {
        "valor_livre": livre,
        "valor_comprometido": comprometido,
        "valor_constituido": constituido,
        "nivel_comprometimento": _nivel(comprometido, constituido),
        "por_janela": janelas,
        "por_arranjo": arranjos,
    }
