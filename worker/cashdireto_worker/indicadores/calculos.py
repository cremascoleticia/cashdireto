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
    # (AP013A e AP007: a área pediu para não calcular indicadores agora.)
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
