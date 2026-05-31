"""Parser da fonte AP007 (contratos/efeitos sobre as unidades de recebíveis).

Puro: não toca em banco. Campos vêm do dicionário oficial CERC (docs/fontes/AP007.md).
⚠️ Layout FÍSICO assumido = padrão AP005 (CSV ';' sem cabeçalho, 22 colunas; col.6 e col.17
quotadas contêm listas). Confirmar com amostra real — ver suposições na ficha.

- col.6 = lista de identificadores do contrato anterior (itens separados por '|').
- col.17 = lista de parcelas (sub-registros '|'; cada um com 2 posições 'data;valor').
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import date

from .._cerc import CercParseError, Fields, clean as _s, data_referencia as _data_ref, sha256_hex, to_text

N_COLS = 22
N_SUB_PARCELA = 2


class Ap007ParseError(CercParseError):
    """Erro de parsing do AP007 (nº de colunas/sub-campos inesperado, valor inválido)."""


_f = Fields(Ap007ParseError)
_dec = _f.dec
_date = _f.date


@dataclass(frozen=True)
class Ap007Parcela:
    ordem: int
    data_parcela: date | None
    valor_parcela: float | None


@dataclass(frozen=True)
class Ap007Contrato:
    linha: int
    tipo_operacao: str | None
    referencia_externa: str | None
    identificador_contrato: str | None
    contratante_doc: str
    repactuacao: str | None
    identificadores_contrato_anterior: list  # list[str]
    participante_doc: str | None
    detentor_doc: str | None
    tipo_efeito: str | None
    saldo_devedor: float | None
    limite_operacao_garantida: float | None
    valor_a_manter: float | None
    data_assinatura: date | None
    data_vencimento: date | None
    tipo_servico: str | None
    modalidade_operacao: str | None
    carteira: str | None
    tipo_avaliacao: str | None
    taxa_juros: float | None
    indexador: str | None
    aceite_incondicional: str | None
    parcelas: list = field(default_factory=list)


@dataclass
class Ap007ParseResult:
    sha256: str
    data_referencia: date
    contratos: list
    contratantes: set
    total_parcelas: int


def _lista_strings(campo: str | None) -> list:
    """col.6 — itens separados por '|'; vazios descartados."""
    v = _s(campo)
    if v is None:
        return []
    return [item for item in (p.strip() for p in v.split("|")) if item]


def _parcelas(campo: str | None) -> list:
    """col.17 — sub-registros '|'; cada um 'data;valor' (2 posições)."""
    v = _s(campo)
    if v is None:
        return []
    parcelas = []
    for ordem, sub in enumerate(v.split("|"), start=1):
        if not sub.strip():
            continue
        campos = sub.split(";")
        if len(campos) > N_SUB_PARCELA:
            raise Ap007ParseError(f"parcela com {len(campos)} campos (>2): {sub[:80]!r}")
        campos += [None] * (N_SUB_PARCELA - len(campos))
        parcelas.append(Ap007Parcela(
            ordem=ordem,
            data_parcela=_date(campos[0]),
            valor_parcela=_dec(campos[1]),
        ))
    return parcelas


def parse(content: str | bytes, *, original_filename: str | None, fallback_date: date) -> Ap007ParseResult:
    raw, text = to_text(content)
    sha = sha256_hex(raw)

    reader = csv.reader(io.StringIO(text), delimiter=";")
    contratos = []
    contratantes = set()
    total_parc = 0
    for i, row in enumerate(reader, start=1):
        if not row or (len(row) == 1 and not row[0].strip()):
            continue  # linha vazia
        if len(row) != N_COLS:
            raise Ap007ParseError(f"linha {i}: {len(row)} colunas (esperado {N_COLS})")
        contratante = _s(row[3])
        if contratante is None:
            raise Ap007ParseError(f"linha {i}: contratante (col4) vazio")
        parcelas = _parcelas(row[16])
        total_parc += len(parcelas)
        contratantes.add(contratante)
        contratos.append(Ap007Contrato(
            linha=i,
            tipo_operacao=_s(row[0]),
            referencia_externa=_s(row[1]),
            identificador_contrato=_s(row[2]),
            contratante_doc=contratante,
            repactuacao=_s(row[4]),
            identificadores_contrato_anterior=_lista_strings(row[5]),
            participante_doc=_s(row[6]),
            detentor_doc=_s(row[7]),
            tipo_efeito=_s(row[8]),
            saldo_devedor=_dec(row[9]),
            limite_operacao_garantida=_dec(row[10]),
            valor_a_manter=_dec(row[11]),
            data_assinatura=_date(row[12]),
            data_vencimento=_date(row[13]),
            tipo_servico=_s(row[14]),
            modalidade_operacao=_s(row[15]),
            carteira=_s(row[17]),
            tipo_avaliacao=_s(row[18]),
            taxa_juros=_dec(row[19]),
            indexador=_s(row[20]),
            aceite_incondicional=_s(row[21]),
            parcelas=parcelas,
        ))
    if not contratos:
        raise Ap007ParseError("arquivo sem registros de contrato")
    return Ap007ParseResult(
        sha256=sha, data_referencia=_data_ref(original_filename, fallback_date),
        contratos=contratos, contratantes=contratantes, total_parcelas=total_parc,
    )
