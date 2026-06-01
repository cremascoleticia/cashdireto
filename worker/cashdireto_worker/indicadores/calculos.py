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

from typing import Iterable, Mapping, Sequence

Resultado = tuple[float | None, dict]


def _soma(rows: Iterable[Mapping], campo: str) -> float:
    """Soma um campo numérico ignorando None."""
    return sum(r[campo] for r in rows if r.get(campo) is not None)


# Concentração/agenda do RADAR ficam em indicadores/radar.py (definição da área: totais por
# situação/janela e constituído por arranjo com %). HHI por credenciadora e bucketização de
# agenda foram removidos (não fazem parte do spec da área).


# ───────────────────────── Oneração própria × terceiros (AP005) ─────────────────────────
# Métrica de risco (base do gatilho de erosão da Fase 3). As somas agrupadas de AP005 (estoque,
# onerado por ordem/tipo/beneficiário) ficam em indicadores/ap005.py, conforme spec da área.

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
    # AP005 — definições da área (ver indicadores/ap005.py). AP005 tem amostra real → disponível.
    # Mesma função por estabelecimento e por raiz (muda só quais linhas entram).
    {"nome": "ap005_constituido_por_usuario_final", "status": "disponivel", "fontes": ["AP005"],
     "modulo": "ap005.constituido_por_usuario_final"},
    {"nome": "ap005_constituido_por_titular_ur", "status": "disponivel", "fontes": ["AP005"],
     "modulo": "ap005.constituido_por_titular_ur"},
    {"nome": "ap005_livre_por_usuario_final", "status": "disponivel", "fontes": ["AP005"],
     "modulo": "ap005.livre_por_usuario_final"},
    {"nome": "ap005_total_ur_por_usuario_final", "status": "disponivel", "fontes": ["AP005"],
     "modulo": "ap005.total_ur_por_usuario_final"},
    {"nome": "ap005_efeito_por_ordem", "status": "disponivel", "fontes": ["AP005"],
     "modulo": "ap005.constituido_efeito_por_ordem"},
    {"nome": "ap005_onerado_por_ordem_regra", "status": "disponivel", "fontes": ["AP005"],
     "modulo": "ap005.onerado_por_ordem_e_regra"},
    {"nome": "ap005_onerado_por_tipo_regra", "status": "disponivel", "fontes": ["AP005"],
     "modulo": "ap005.onerado_por_tipo_info_e_regra"},
    {"nome": "ap005_efeito_por_ordem_beneficiario", "status": "disponivel", "fontes": ["AP005"],
     "modulo": "ap005.constituido_efeito_por_ordem_e_beneficiario"},
    {"nome": "ap005_efeito_por_beneficiario", "status": "disponivel", "fontes": ["AP005"],
     "modulo": "ap005.constituido_efeito_por_beneficiario"},
    # próprio×terceiros: métrica de risco (base do gatilho de erosão da Fase 3); usa detentor_proprio.
    {"nome": "onerado_proprio", "status": "disponivel_com_parametro", "fontes": ["AP005"],
     "parametro": "detentor_proprio"},
    {"nome": "onerado_terceiros", "status": "disponivel_com_parametro", "fontes": ["AP005"],
     "parametro": "detentor_proprio"},
    # AP013 (legado) — definições da área (ver indicadores/ap013.py). Sem amostra real → pendente.
    {"nome": "ap013_constituido_por_usuario_final", "status": "disponivel_pendente_validacao",
     "fontes": ["AP013"], "modulo": "ap013.constituido_por_usuario_final"},
    {"nome": "ap013_constituido_por_uf_oneracao", "status": "disponivel_pendente_validacao",
     "fontes": ["AP013"], "modulo": "ap013.constituido_por_usuario_final_e_oneracao"},
    {"nome": "ap013_onerado_por_usuario_final", "status": "disponivel_pendente_validacao",
     "fontes": ["AP013"], "modulo": "ap013.onerado_por_usuario_final"},
    {"nome": "ap013_onerado_por_uf_oneracao", "status": "disponivel_pendente_validacao",
     "fontes": ["AP013"], "modulo": "ap013.onerado_por_usuario_final_e_oneracao"},
    {"nome": "ap013_onerado_por_uf_mes_oneracao", "status": "disponivel_pendente_validacao",
     "fontes": ["AP013"], "modulo": "ap013.onerado_por_usuario_final_data_oneracao"},
    {"nome": "ap013_constituido_por_uf_mes_oneracao", "status": "disponivel_pendente_validacao",
     "fontes": ["AP013"], "modulo": "ap013.constituido_por_usuario_final_data_oneracao"},
    {"nome": "ap013_valor_a_manter_proprio", "status": "disponivel_com_parametro",
     "fontes": ["AP013"], "parametro": "detentor_proprio",
     "modulo": "ap013.valor_a_manter_proprio_por_contratante_efeito"},
    # AP013B — definição da área (ver indicadores/ap013b.py)
    {"nome": "ap013b_calculado_credenciadoras_proprio", "status": "disponivel_com_parametro",
     "fontes": ["AP013B"], "parametro": "detentor_proprio",
     "modulo": "ap013b.calculado_credenciadoras_proprio_por_contratante_efeito"},
    # AP013C — definição da área (ver indicadores/ap013c.py)
    {"nome": "ap013c_total_constituido_efeitos_depois", "status": "disponivel_pendente_validacao",
     "fontes": ["AP013C"], "modulo": "ap013c.total_constituido_efeitos_depois"},
    {"nome": "ap013c_total_suficiencia_depois", "status": "disponivel_pendente_validacao",
     "fontes": ["AP013C"], "modulo": "ap013c.total_suficiencia_depois"},
    # extras herdados do SPEC (NÃO estão nas definições da área) — confirmar manter/remover.
    # (AP013A/AP007 a área disse para não calcular agora.)
    {"nome": "cobertura_redistribuicao", "status": "disponivel_spec_extra", "fontes": ["AP013C"]},
    {"nome": "headroom_redistribuicao", "status": "disponivel_spec_extra", "fontes": ["AP013C"]},
    {"nome": "efeito_redistribuicao", "status": "disponivel_spec_extra", "fontes": ["AP013C"]},
    {"nome": "sobrecolateralizacao", "status": "disponivel_spec_extra", "fontes": ["AP013B"]},
    {"nome": "aderencia_oneracao", "status": "disponivel_spec_extra", "fontes": ["AP013A"]},
    {"nome": "prioridade_1_share", "status": "disponivel_spec_extra", "fontes": ["AP013B"]},
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
    # explicitamente desabilitado (regra 9): concentração por bandeira (% por bandeira, análogo
    # ao "% por arranjo") depende do de-para arranjo→bandeira que ainda não temos.
    {"nome": "concentracao_bandeira", "status": "indisponivel", "fontes": ["RADAR"],
     "motivo": "falta de-para arranjo→bandeira (domínio CERC)"},
]
