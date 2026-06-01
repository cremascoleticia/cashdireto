"""Cálculo determinístico de indicadores (Fase 2).

Regra inviolável do projeto: **a LLM nunca calcula indicador**; todo número vem daqui —
Python puro, testado e auditável. Estas funções NÃO tocam em banco: recebem linhas canônicas
já carregadas (listas de dicts no formato das tabelas core.*) e devolvem `(valor, detalhe)`,
onde `valor` é o número que vai para core.indicador_snapshot.valor e `detalhe` o jsonb de apoio.

Status de cada indicador (ver docs/reconciliacao.md) está em CATALOGO. Indicadores marcados
`indisponivel` NÃO são calculados (ficam explicitamente desabilitados — regra 9); os que dependem
de parâmetro/​histórico devolvem `valor=None` com o motivo no detalhe quando o insumo falta.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Mapping, Sequence

Resultado = tuple[float | None, dict]

# Mapa janela RADAR → bucket de agenda (SPEC: D+1–30, 31–60, 61–90, 90+).
_BUCKET = {
    "0_30": "d1_30",
    "31_60": "d31_60",
    "61_90": "d61_90",
    "91_120": "d90_mais",
    "120_mais": "d90_mais",
}


def _soma(rows: Iterable[Mapping], campo: str) -> float:
    """Soma um campo numérico ignorando None."""
    return sum(r[campo] for r in rows if r.get(campo) is not None)


def hhi(valores_por_chave: Mapping[str, float]) -> float | None:
    """Índice Herfindahl-Hirschman normalizado em [0,1] (Σ share²). 1 = concentração total."""
    total = sum(v for v in valores_por_chave.values() if v)
    if not total:
        return None
    return sum((v / total) ** 2 for v in valores_por_chave.values() if v)


# ───────────────────────── Concentração ─────────────────────────

def hhi_credenciadora(agenda_rows: Sequence[Mapping]) -> Resultado:
    """HHI da concentração de valor por credenciadora (RADAR agenda_ur)."""
    por_cred: dict[str, float] = defaultdict(float)
    for r in agenda_rows:
        if r.get("valor"):
            por_cred[r.get("credenciadora_doc") or "(sem)"] += r["valor"]
    valor = hhi(por_cred)
    return valor, {"por_credenciadora": dict(por_cred), "n_credenciadoras": len(por_cred)}


# ───────────────────────── Agenda futura ─────────────────────────

def agenda_por_bucket(agenda_rows: Sequence[Mapping]) -> Resultado:
    """Distribuição da agenda por bucket de janela, por situação (RADAR).

    Não soma situações entre si (constituido ≠ livre+comprometido na amostra). `valor` headline
    = total da situação 'constituido'; o detalhe traz {situacao: {bucket: valor}}.
    """
    por: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for r in agenda_rows:
        bucket = _BUCKET.get(r.get("janela"))
        if bucket is None or not r.get("valor"):
            continue
        por[r.get("situacao") or "(sem)"][bucket] += r["valor"]
    detalhe = {sit: dict(buckets) for sit, buckets in por.items()}
    valor = sum(detalhe.get("constituido", {}).values()) or None
    return valor, {"por_situacao_bucket": detalhe}


# ───────────────────────── Estoque / oneração (AP005) ─────────────────────────

def estoque_total(ur_rows: Sequence[Mapping]) -> Resultado:
    """Σ valor constituído total das URs (AP005 ap005_ur)."""
    total = _soma(ur_rows, "valor_constituido_total")
    return (total or None), {"n_urs": len(ur_rows)}


def estoque_onerado(pagamento_rows: Sequence[Mapping]) -> Resultado:
    """Σ valor onerado nos efeitos (AP005 ap005_pagamento)."""
    onerado = _soma(pagamento_rows, "valor_onerado")
    return (onerado or None), {"n_efeitos": len(pagamento_rows)}


def pct_onerado(ur_rows: Sequence[Mapping], pagamento_rows: Sequence[Mapping]) -> Resultado:
    """estoque_onerado / estoque_total."""
    total = _soma(ur_rows, "valor_constituido_total")
    onerado = _soma(pagamento_rows, "valor_onerado")
    if not total:
        return None, {"motivo": "estoque_total = 0"}
    return onerado / total, {"onerado": onerado, "total": total}


def onerado_proprio(pagamento_rows: Sequence[Mapping], detentor_proprio: Sequence[str] | None) -> Resultado:
    """Σ onerado cujo beneficiário é a cashdireto. Sem o parâmetro → indisponível (não estima)."""
    if not detentor_proprio:
        return None, {"motivo": "parametro detentor_proprio não definido"}
    proprios = set(detentor_proprio)
    valor = sum(r["valor_onerado"] for r in pagamento_rows
                if r.get("valor_onerado") is not None and r.get("beneficiario_doc") in proprios)
    return valor, {"detentor_proprio": sorted(proprios)}


def onerado_terceiros(pagamento_rows: Sequence[Mapping], detentor_proprio: Sequence[str] | None) -> Resultado:
    """estoque_onerado − onerado_proprio. Sem o parâmetro → indisponível."""
    if not detentor_proprio:
        return None, {"motivo": "parametro detentor_proprio não definido"}
    proprio, _ = onerado_proprio(pagamento_rows, detentor_proprio)
    total = _soma(pagamento_rows, "valor_onerado")
    return total - (proprio or 0.0), {"onerado_total": total, "onerado_proprio": proprio}


# ───────────────────────── Cobertura / headroom (AP013C) ─────────────────────────

def cobertura_redistribuicao(redistribuicao_rows: Sequence[Mapping]) -> Resultado:
    """Cobertura pós-redistribuição = Σ constituído depois / Σ valor mínimo a manter (AP013C)."""
    total_min = _soma(redistribuicao_rows, "valor_minimo_a_manter")
    total_const = _soma(redistribuicao_rows, "valor_constituido_efeitos_depois")
    if not total_min:
        return None, {"motivo": "Σ valor_minimo_a_manter = 0"}
    return total_const / total_min, {"constituido_depois": total_const, "minimo": total_min}


def headroom_redistribuicao(redistribuicao_rows: Sequence[Mapping]) -> Resultado:
    """Headroom pós-redistribuição = Σ valor_suficiencia_depois (AP013C col.14; <0 déficit)."""
    suf = _soma(redistribuicao_rows, "valor_suficiencia_depois")
    return suf, {"n_contratos": len(redistribuicao_rows)}


def efeito_redistribuicao(redistribuicao_rows: Sequence[Mapping]) -> Resultado:
    """Σ (suficiência depois − suficiência antes) — quanto a redistribuição melhorou a cobertura."""
    depois = _soma(redistribuicao_rows, "valor_suficiencia_depois")
    antes = _soma(redistribuicao_rows, "valor_suficiencia_antes")
    return depois - antes, {"antes": antes, "depois": depois}


# ───────────────────────── Sobrecolateralização / aderência / prioridade ─────────────────────────

def sobrecolateralizacao(contrato_rows: Sequence[Mapping]) -> Resultado:
    """Sobrecolateralização do titular = média ponderada por saldo do indicador (AP013B col.17)."""
    num = sum((r["indicador_sobrecolateralizacao"] or 0) * (r.get("saldo_devedor") or 0)
              for r in contrato_rows if r.get("indicador_sobrecolateralizacao") is not None)
    saldo = _soma(contrato_rows, "saldo_devedor")
    if not saldo:
        return None, {"motivo": "Σ saldo_devedor = 0"}
    return num / saldo, {"saldo_total": saldo}


def aderencia_oneracao(resumo_rows: Sequence[Mapping]) -> Resultado:
    """Aderência = Σ calculado credenciadoras / Σ calculado CERC (AP013A; esperado ≈ 1)."""
    cerc = _soma(resumo_rows, "valor_efeitos_calculados_cerc")
    cred = _soma(resumo_rows, "valor_efeitos_calculados_credenciadoras")
    if not cerc:
        return None, {"motivo": "Σ calculado CERC = 0"}
    return cred / cerc, {"calculado_cerc": cerc, "calculado_credenciadoras": cred}


def prioridade_1_share(credenciadora_rows: Sequence[Mapping]) -> Resultado:
    """Fração de URs em 1ª prioridade = Σ p1 / Σ(p1 + p≠1) (AP013B credenciadora)."""
    p1 = _soma(credenciadora_rows, "qtd_ur_prioridade_1")
    pd = _soma(credenciadora_rows, "qtd_ur_prioridade_diferente_1")
    if not (p1 + pd):
        return None, {"motivo": "sem URs alcançadas"}
    return p1 / (p1 + pd), {"prioridade_1": p1, "prioridade_diferente_1": pd}


# ───────────────────────── Catálogo (status por indicador — ver docs/reconciliacao.md) ─────────────────────────

CATALOGO = [
    # nome, status, fonte(s), função (ou None se ainda não calculado)
    # RADAR — definições da área (ver indicadores/radar.py): totais por situação, nível de
    # comprometimento (total e por janela), valores por janela e constituído por arranjo (%).
    {"nome": "radar_recebiveis", "status": "disponivel", "fontes": ["RADAR"],
     "modulo": "radar.indicadores_radar",
     "nota": "mesma função por estabelecimento e por raiz (muda só quais linhas entram)"},
    # extras herdados do SPEC (NÃO estão no spec da área para RADAR) — confirmar manter/remover:
    {"nome": "agenda_por_bucket", "status": "disponivel_spec_extra", "fontes": ["RADAR"]},
    {"nome": "hhi_credenciadora", "status": "disponivel_spec_extra", "fontes": ["RADAR"]},
    {"nome": "estoque_total", "status": "disponivel_pendente_validacao", "fontes": ["AP005"]},
    {"nome": "estoque_onerado", "status": "disponivel_pendente_validacao", "fontes": ["AP005"]},
    {"nome": "pct_onerado", "status": "disponivel_pendente_validacao", "fontes": ["AP005"]},
    {"nome": "onerado_proprio", "status": "disponivel_com_parametro", "fontes": ["AP005"],
     "parametro": "detentor_proprio"},
    {"nome": "onerado_terceiros", "status": "disponivel_com_parametro", "fontes": ["AP005"],
     "parametro": "detentor_proprio"},
    {"nome": "cobertura_redistribuicao", "status": "disponivel_pendente_validacao", "fontes": ["AP013C"]},
    {"nome": "headroom_redistribuicao", "status": "disponivel_pendente_validacao", "fontes": ["AP013C"]},
    {"nome": "efeito_redistribuicao", "status": "disponivel_pendente_validacao", "fontes": ["AP013C"]},
    {"nome": "sobrecolateralizacao", "status": "disponivel_pendente_validacao", "fontes": ["AP013B"]},
    {"nome": "aderencia_oneracao", "status": "disponivel_pendente_validacao", "fontes": ["AP013A"]},
    {"nome": "prioridade_1_share", "status": "disponivel_pendente_validacao", "fontes": ["AP013B"]},
    # RAIOX — definições da área (ver indicadores/raiox.py). Série mensal vem dentro do próprio
    # arquivo (não depende de múltiplos snapshots).
    {"nome": "raiox_estabelecimento", "status": "disponivel", "fontes": ["RAIOX"],
     "modulo": "raiox.por_estabelecimento",
     "nota": "9 indicadores do dossiê + série mensal + sócios/IP/financiadores, por CNPJ"},
    {"nome": "raiox_raiz", "status": "disponivel", "fontes": ["RAIOX"],
     "modulo": "raiox.agregar_por_raiz",
     "nota": "agregação por raiz de CNPJ; índice de conformidade fica só por estabelecimento"},
    # depende de série temporal (≥2 snapshots) — fatia futura
    {"nome": "taxa_realizacao", "status": "pendente_historico", "fontes": ["AP005", "RADAR"]},
    # explicitamente desabilitado (regra 9): falta de-para arranjo→bandeira
    {"nome": "hhi_bandeira", "status": "indisponivel", "fontes": ["RADAR"],
     "motivo": "falta de-para arranjo→bandeira (domínio CERC)"},
]
