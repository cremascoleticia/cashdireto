"""Parser da fonte AP013 (legado) — situação dos contratos + URs alcançadas (com prioridade de ônus).

Puro: não toca em banco. Campos vêm do dicionário oficial CERC (docs/fontes/AP013.md).
⚠️ Layout FÍSICO assumido = padrão AP005/AP007 (CSV ';' sem cabeçalho, 17 colunas; col.13 e
col.14 quotadas contêm listas). Confirmar com amostra real — ver suposições na ficha.

- col.13 = lista de URs alcançadas (sub-registros '|'; cada um com 14 posições ';'). Estruturado.
- col.14 = indicadores de consistência → guardado BRUTO (14.3 usa '|'/':' internamente, ambíguo
  sem amostra). Parse estruturado adiado.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import date

from .._cerc import CercParseError, Fields, clean as _s, data_referencia as _data_ref, sha256_hex, to_text

N_COLS = 17
N_SUB_UR = 14


class Ap013ParseError(CercParseError):
    """Erro de parsing do AP013 (nº de colunas/sub-campos inesperado, valor inválido)."""


_f = Fields(Ap013ParseError)
_dec = _f.dec
_date = _f.date


@dataclass(frozen=True)
class Ap013Ur:
    ordem: int
    entidade_registradora_doc: str | None
    credenciadora_doc: str | None
    usuario_final_doc: str | None
    arranjo: str | None
    data_liquidacao: date | None
    titular_ur_doc: str | None
    constituicao: str | None
    valor_constituido_total: float | None
    valor_bloqueado: float | None
    indicador_oneracao: str | None
    regra_divisao: str | None
    valor_onerado: float | None
    referencia_externa: str | None
    valor_constituido_efeito: float | None


@dataclass(frozen=True)
class Ap013Contrato:
    linha: int
    referencia_externa: str | None
    identificador_contrato: str | None
    contratante_doc: str
    repactuacao: str | None
    identificador_contrato_anterior: str | None
    participante_doc: str | None
    detentor_doc: str | None
    tipo_efeito: str | None
    saldo_devedor: float | None
    limite_operacao_garantida: float | None
    valor_a_manter: float | None
    data_vencimento: date | None
    indicadores_consistencia_raw: str | None
    qtd_ur_alcancadas: float | None
    valor_ur_alcancadas: float | None
    resultado_distribuicao_onus: str | None
    urs: list = field(default_factory=list)


@dataclass
class Ap013ParseResult:
    sha256: str
    data_referencia: date
    contratos: list
    contratantes: set
    total_urs: int


def _urs(compound: str | None) -> list:
    """col.13 — sub-registros '|'; cada um com 14 posições ';' (faltando finais → NULL)."""
    comp = _s(compound)
    if comp is None:
        return []
    urs = []
    for ordem, sub in enumerate(comp.split("|"), start=1):
        if not sub.strip():
            continue
        campos = sub.split(";")
        if len(campos) > N_SUB_UR:
            raise Ap013ParseError(f"UR com {len(campos)} campos (>14): {sub[:80]!r}")
        campos += [None] * (N_SUB_UR - len(campos))
        urs.append(Ap013Ur(
            ordem=ordem,
            entidade_registradora_doc=_s(campos[0]),
            credenciadora_doc=_s(campos[1]),
            usuario_final_doc=_s(campos[2]),
            arranjo=_s(campos[3]),
            data_liquidacao=_date(campos[4]),
            titular_ur_doc=_s(campos[5]),
            constituicao=_s(campos[6]),
            valor_constituido_total=_dec(campos[7]),
            valor_bloqueado=_dec(campos[8]),
            indicador_oneracao=_s(campos[9]),
            regra_divisao=_s(campos[10]),
            valor_onerado=_dec(campos[11]),
            referencia_externa=_s(campos[12]),
            valor_constituido_efeito=_dec(campos[13]),
        ))
    return urs


def parse(content: str | bytes, *, original_filename: str | None, fallback_date: date) -> Ap013ParseResult:
    raw, text = to_text(content)
    sha = sha256_hex(raw)

    reader = csv.reader(io.StringIO(text), delimiter=";")
    contratos = []
    contratantes = set()
    total_urs = 0
    for i, row in enumerate(reader, start=1):
        if not row or (len(row) == 1 and not row[0].strip()):
            continue  # linha vazia
        if len(row) != N_COLS:
            raise Ap013ParseError(f"linha {i}: {len(row)} colunas (esperado {N_COLS})")
        contratante = _s(row[2])
        if contratante is None:
            raise Ap013ParseError(f"linha {i}: contratante (col3) vazio")
        urs = _urs(row[12])
        total_urs += len(urs)
        contratantes.add(contratante)
        contratos.append(Ap013Contrato(
            linha=i,
            referencia_externa=_s(row[0]),
            identificador_contrato=_s(row[1]),
            contratante_doc=contratante,
            repactuacao=_s(row[3]),
            identificador_contrato_anterior=_s(row[4]),
            participante_doc=_s(row[5]),
            detentor_doc=_s(row[6]),
            tipo_efeito=_s(row[7]),
            saldo_devedor=_dec(row[8]),
            limite_operacao_garantida=_dec(row[9]),
            valor_a_manter=_dec(row[10]),
            data_vencimento=_date(row[11]),
            indicadores_consistencia_raw=_s(row[13]),   # col14 BRUTO
            qtd_ur_alcancadas=_dec(row[14]),
            valor_ur_alcancadas=_dec(row[15]),
            resultado_distribuicao_onus=_s(row[16]),
            urs=urs,
        ))
    if not contratos:
        raise Ap013ParseError("arquivo sem registros de contrato")
    return Ap013ParseResult(
        sha256=sha, data_referencia=_data_ref(original_filename, fallback_date),
        contratos=contratos, contratantes=contratantes, total_urs=total_urs,
    )
