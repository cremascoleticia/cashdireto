"""Indicadores da fonte RAIOX (Fase 2) — por estabelecimento e por raiz de CNPJ.

Funções puras (sem banco). Definições fornecidas pela área (2026-06-01):

Por estabelecimento comercial (1 CNPJ = 1 arquivo): os indicadores do dossiê tal como extraídos
(nível de comprometimento, faturamento estimado, potencial de chargeback, faturamento médio
diário, agenda mensal média, volume de antecipação, constatações críticas, fraudes detectadas,
índice de conformidade e risco), a série mensal (histórico de agenda e volume antecipado) e o
quadro de relacionamento (sócios), instituições de pagamento e financiadores.

Por raiz de CNPJ (matriz + filiais — mesmos 8 primeiros dígitos), agregando os estabelecimentos:
- SOMA: faturamento estimado, faturamento médio diário, agenda mensal média, volume de
  antecipação, constatações críticas, fraudes detectadas; e a série mensal (soma por mês).
- MÉDIA PONDERADA pelo faturamento médio diário: nível de comprometimento, potencial de chargeback.
- Quadro de relacionamento (sócios): união sem duplicidades.
- Instituição de pagamento / Financiadores: lista todas, com percentual PONDERADO pelo volume
  antecipado — Σ(percentual × volume_estab) / Σ(volume de todos os estabelecimentos).
- Índice de conformidade e risco: NÃO agregado por raiz (fica só por estabelecimento).

Formato de entrada (`dossie`), montado pelo runner a partir das tabelas raiox_*:
    {
      "cnpj": "11.111.111/0001-11",
      "indicadores": {"nivel_comprometimento": .., "faturamento_estimado": .., ...},
      "serie_mensal": [{"competencia": date, "serie": "agenda"|"volume_antecipacao", "valor": ..}],
      "relacionamentos": [{"tipo": "socio_comum"|"instituicao_pagamento"|"financiador",
                            "nome": "..", "percentual": ..}],
    }
"""
from __future__ import annotations

from collections import defaultdict
from typing import Mapping, Sequence

# Indicadores escalares somados na agregação por raiz.
SOMA = (
    "faturamento_estimado", "faturamento_medio_diario", "agenda_mensal_media",
    "volume_antecipacao", "constatacoes_criticas", "fraudes_detectadas",
)
# Indicadores ponderados pelo faturamento médio diário (fmd) na agregação por raiz.
PONDERADO_FMD = ("nivel_comprometimento", "potencial_chargeback")


def raiz_cnpj(cnpj: str | None) -> str | None:
    """Raiz do CNPJ = 8 primeiros dígitos (ignora pontuação)."""
    if not cnpj:
        return None
    digitos = "".join(ch for ch in cnpj if ch.isdigit())
    return digitos[:8] if len(digitos) >= 8 else None


def por_estabelecimento(dossie: Mapping) -> dict:
    """Indicadores por estabelecimento: passthrough estruturado do dossiê parseado."""
    ind = dict(dossie.get("indicadores") or {})
    return {
        "cnpj": dossie.get("cnpj"),
        "indicadores": ind,
        "serie_mensal": list(dossie.get("serie_mensal") or []),
        "relacionamentos": list(dossie.get("relacionamentos") or []),
    }


def _media_ponderada(dossies: Sequence[Mapping], chave: str, peso: str) -> float | None:
    num = 0.0
    den = 0.0
    for d in dossies:
        ind = d.get("indicadores") or {}
        x, w = ind.get(chave), ind.get(peso)
        if x is not None and w:
            num += x * w
            den += w
    return (num / den) if den else None


def _percentual_ponderado_por_volume(dossies: Sequence[Mapping], tipo: str) -> list[dict]:
    """Percentual de cada nome ponderado pelo volume antecipado do estabelecimento."""
    vol_total = sum((d.get("indicadores") or {}).get("volume_antecipacao") or 0 for d in dossies)
    acc: dict[str, float] = defaultdict(float)
    for d in dossies:
        vol = (d.get("indicadores") or {}).get("volume_antecipacao") or 0
        for r in d.get("relacionamentos") or []:
            if r.get("tipo") == tipo and r.get("nome"):
                acc[r["nome"]] += (r.get("percentual") or 0) * vol
    if not vol_total:
        # sem volume não dá para ponderar — devolve nomes com percentual indisponível (não estima)
        return [{"nome": n, "percentual": None} for n in sorted(acc)]
    itens = [{"nome": n, "percentual": v / vol_total} for n, v in acc.items()]
    return sorted(itens, key=lambda x: x["percentual"], reverse=True)


def agregar_por_raiz(dossies: Sequence[Mapping]) -> dict:
    """Agrega uma lista de dossiês (mesma raiz de CNPJ) conforme as regras da área."""
    indicadores: dict[str, float | None] = {}

    for chave in SOMA:
        indicadores[chave] = sum((d.get("indicadores") or {}).get(chave) or 0 for d in dossies)

    for chave in PONDERADO_FMD:
        indicadores[chave] = _media_ponderada(dossies, chave, "faturamento_medio_diario")

    # série mensal somada por (competência, série)
    serie: dict[tuple, float] = defaultdict(float)
    for d in dossies:
        for s in d.get("serie_mensal") or []:
            if s.get("valor") is not None:
                serie[(s.get("competencia"), s.get("serie"))] += s["valor"]
    serie_mensal = [
        {"competencia": comp, "serie": ser, "valor": val}
        for (comp, ser), val in sorted(serie.items(), key=lambda kv: (str(kv[0][0]), kv[0][1]))
    ]

    # sócios: união sem duplicidade
    socios = sorted({
        r["nome"] for d in dossies for r in (d.get("relacionamentos") or [])
        if r.get("tipo") == "socio_comum" and r.get("nome")
    })

    return {
        "raiz_cnpj": raiz_cnpj(dossies[0].get("cnpj")) if dossies else None,
        "n_estabelecimentos": len(dossies),
        "indicadores": indicadores,                       # índice de conformidade NÃO entra (decisão da área)
        "serie_mensal": serie_mensal,
        "socios": socios,
        "instituicoes_pagamento": _percentual_ponderado_por_volume(dossies, "instituicao_pagamento"),
        "financiadores": _percentual_ponderado_por_volume(dossies, "financiador"),
    }
