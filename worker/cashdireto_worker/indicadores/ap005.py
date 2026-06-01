"""Indicadores da fonte AP005 (Fase 2) — agenda de URs e efeitos.

Funções puras (sem banco). Definições fornecidas pela área (2026-06-01). Como no RADAR, a mesma
função serve por estabelecimento e por raiz de CNPJ — muda só QUAIS linhas entram (o runner
filtra por um usuário final / por todos os da raiz).

Nível UR (linhas de core.ap005_ur): valores agrupados por usuário final recebedor ou por titular
da UR, com soma total E por (ano-mês) da data de liquidação.

Nível efeito (linhas de core.ap005_pagamento): valores agrupados por indicador de ordem do efeito,
tipo de informação de pagamento, regra de divisão e/ou beneficiário.

Cada função devolve {"total": <grand total>, "grupos": ...} — JSON-friendly para o detalhe do snapshot.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Mapping, Sequence


def _ym(d) -> str | None:
    """date → 'AAAA-MM' (ano-mês); None se sem data."""
    return f"{d.year:04d}-{d.month:02d}" if d is not None else None


def _por_chave_com_mes(rows: Sequence[Mapping], chave: str, valor: str,
                       data: str = "data_liquidacao") -> dict:
    """Soma `valor` por `chave`, com total e quebra por ano-mês de `data`."""
    grupos: dict = {}
    grand = 0.0
    for r in rows:
        v = r.get(valor)
        if v is None:
            continue
        g = grupos.setdefault(r.get(chave), {"total": 0.0, "por_mes": defaultdict(float)})
        g["total"] += v
        ym = _ym(r.get(data))
        if ym:
            g["por_mes"][ym] += v
        grand += v
    for g in grupos.values():
        g["por_mes"] = dict(sorted(g["por_mes"].items()))
    return {"total": grand, "grupos": grupos}


def _agrupar_soma(rows: Sequence[Mapping], chaves: list[str], valor: str) -> dict:
    """Soma `valor` agrupando pela tupla de `chaves`; devolve lista de grupos + total geral."""
    acc: dict[tuple, float] = defaultdict(float)
    grand = 0.0
    for r in rows:
        v = r.get(valor)
        if v is None:
            continue
        acc[tuple(r.get(c) for c in chaves)] += v
        grand += v
    grupos = [{**dict(zip(chaves, k)), "valor": val} for k, val in acc.items()]
    grupos.sort(key=lambda g: g["valor"], reverse=True)
    return {"total": grand, "grupos": grupos}


# ───────────────────────── Nível UR (ap005_ur) ─────────────────────────

def constituido_por_usuario_final(ur_rows: Sequence[Mapping]) -> dict:
    """Valor constituído total por usuário final recebedor (total e por ano-mês)."""
    return _por_chave_com_mes(ur_rows, "usuario_final_doc", "valor_constituido_total")


def constituido_por_titular_ur(ur_rows: Sequence[Mapping]) -> dict:
    """Valor constituído total por titular da UR (total e por ano-mês)."""
    return _por_chave_com_mes(ur_rows, "titular_ur_doc", "valor_constituido_total")


def livre_por_usuario_final(ur_rows: Sequence[Mapping]) -> dict:
    """Valor livre total por usuário final recebedor (total e por ano-mês)."""
    return _por_chave_com_mes(ur_rows, "usuario_final_doc", "valor_livre")


def total_ur_por_usuario_final(ur_rows: Sequence[Mapping]) -> dict:
    """Valor total da UR por usuário final recebedor (total e por ano-mês)."""
    return _por_chave_com_mes(ur_rows, "usuario_final_doc", "valor_total_ur")


# ───────────────────────── Nível efeito (ap005_pagamento) ─────────────────────────

def constituido_efeito_por_ordem(pag_rows: Sequence[Mapping]) -> dict:
    """Valor constituído do efeito por indicador de ordem do efeito."""
    return _agrupar_soma(pag_rows, ["indicador_ordem_efeito"], "valor_constituido_efeito")


def onerado_por_ordem_e_regra(pag_rows: Sequence[Mapping]) -> dict:
    """Valor onerado por indicador de ordem do efeito e regra de divisão."""
    return _agrupar_soma(pag_rows, ["indicador_ordem_efeito", "regra_divisao"], "valor_onerado")


def onerado_por_tipo_info_e_regra(pag_rows: Sequence[Mapping]) -> dict:
    """Valor onerado por tipo de informação de pagamento e regra de divisão."""
    return _agrupar_soma(pag_rows, ["tipo_informacao_pagamento", "regra_divisao"], "valor_onerado")


def constituido_efeito_por_ordem_e_beneficiario(pag_rows: Sequence[Mapping]) -> dict:
    """Valor constituído do efeito por indicador de ordem do efeito e beneficiário."""
    return _agrupar_soma(pag_rows, ["indicador_ordem_efeito", "beneficiario_doc"],
                         "valor_constituido_efeito")


def constituido_efeito_por_beneficiario(pag_rows: Sequence[Mapping]) -> dict:
    """Valor constituído do efeito por beneficiário."""
    return _agrupar_soma(pag_rows, ["beneficiario_doc"], "valor_constituido_efeito")
