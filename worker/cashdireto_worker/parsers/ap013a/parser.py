"""Parser da fonte AP013A — resumo agregado por Detentor (financiador).

Puro: não toca em banco. Campos vêm do dicionário oficial CERC (docs/fontes/AP013A.md).
⚠️ Layout FÍSICO assumido = padrão CERC (CSV ';' sem cabeçalho, 10 colunas escalares, sem listas).

1 linha = 1 detentor. NÃO tem contratante/titular — a chave é detentor_doc (col1).
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date

from .._cerc import CercParseError, Fields, clean as _s, data_referencia as _data_ref, sha256_hex, to_text

N_COLS = 10


class Ap013aParseError(CercParseError):
    """Erro de parsing do AP013A (nº de colunas inesperado, valor inválido)."""


_f = Fields(Ap013aParseError)
_dec = _f.dec
_int = _f.intval


@dataclass(frozen=True)
class Ap013aResumo:
    linha: int
    detentor_doc: str
    qtd_contratos: int | None
    qtd_contratantes: int | None
    valor_saldo_devedor_total: float | None
    qtd_ur_constituidas: int | None
    qtd_ur_nao_constituidas: int | None
    qtd_efeitos: int | None
    valor_efeitos_solicitados: float | None
    valor_efeitos_calculados_cerc: float | None
    valor_efeitos_calculados_credenciadoras: float | None


@dataclass
class Ap013aParseResult:
    sha256: str
    data_referencia: date
    resumos: list
    detentores: set


def parse(content: str | bytes, *, original_filename: str | None, fallback_date: date) -> Ap013aParseResult:
    raw, text = to_text(content)
    sha = sha256_hex(raw)

    reader = csv.reader(io.StringIO(text), delimiter=";")
    resumos = []
    detentores = set()
    for i, row in enumerate(reader, start=1):
        if not row or (len(row) == 1 and not row[0].strip()):
            continue  # linha vazia
        if len(row) != N_COLS:
            raise Ap013aParseError(f"linha {i}: {len(row)} colunas (esperado {N_COLS})")
        detentor = _s(row[0])
        if detentor is None:
            raise Ap013aParseError(f"linha {i}: detentor (col1) vazio")
        detentores.add(detentor)
        resumos.append(Ap013aResumo(
            linha=i,
            detentor_doc=detentor,
            qtd_contratos=_int(row[1]),
            qtd_contratantes=_int(row[2]),
            valor_saldo_devedor_total=_dec(row[3]),
            qtd_ur_constituidas=_int(row[4]),
            qtd_ur_nao_constituidas=_int(row[5]),
            qtd_efeitos=_int(row[6]),
            valor_efeitos_solicitados=_dec(row[7]),
            valor_efeitos_calculados_cerc=_dec(row[8]),
            valor_efeitos_calculados_credenciadoras=_dec(row[9]),
        ))
    if not resumos:
        raise Ap013aParseError("arquivo sem registros de resumo")
    return Ap013aParseResult(
        sha256=sha, data_referencia=_data_ref(original_filename, fallback_date),
        resumos=resumos, detentores=detentores,
    )
