"""Parser da fonte AP013C — resultado da redistribuição do Gestão de Colateral (antes x depois).

Puro: não toca em banco. Campos vêm do dicionário oficial CERC (docs/fontes/AP013C.md).
⚠️ Layout FÍSICO assumido = padrão das demais fontes CERC (CSV ';' sem cabeçalho, 19 colunas
escalares, sem listas). Confirmar com amostra real — ver suposições na ficha.

1 linha = 1 contrato. Tem Contratante (col3) → titular (multi-titular).
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date

from .._cerc import CercParseError, Fields, clean as _s, data_referencia as _data_ref, sha256_hex, to_text

N_COLS = 19


class Ap013cParseError(CercParseError):
    """Erro de parsing do AP013C (nº de colunas inesperado, valor inválido)."""


_f = Fields(Ap013cParseError)
_dec = _f.dec
_int = _f.intval
_date = _f.date


@dataclass(frozen=True)
class Ap013cRedistribuicao:
    linha: int
    data_redistribuicao: date | None
    referencia_externa: str | None
    contratante_doc: str
    participante_doc: str | None
    carteira: str | None
    valor_minimo_a_manter: float | None
    valor_suficiencia_antes: float | None
    qtd_ur_constituidas_antes: int | None
    qtd_ur_a_constituir_antes: int | None
    valor_constituido_efeitos_antes: float | None
    valor_livre_agenda_antes: float | None
    qtd_ur_constituidas_solicitadas: int | None
    qtd_ur_a_constituir_solicitadas: int | None
    valor_suficiencia_depois: float | None
    qtd_ur_constituidas_depois: int | None
    qtd_ur_a_constituir_depois: int | None
    valor_constituido_efeitos_depois: float | None
    valor_agenda_anomala: float | None
    observacoes: str | None


@dataclass
class Ap013cParseResult:
    sha256: str
    data_referencia: date
    registros: list
    contratantes: set


def parse(content: str | bytes, *, original_filename: str | None, fallback_date: date) -> Ap013cParseResult:
    raw, text = to_text(content)
    sha = sha256_hex(raw)

    reader = csv.reader(io.StringIO(text), delimiter=";")
    registros = []
    contratantes = set()
    for i, row in enumerate(reader, start=1):
        if not row or (len(row) == 1 and not row[0].strip()):
            continue  # linha vazia
        if len(row) != N_COLS:
            raise Ap013cParseError(f"linha {i}: {len(row)} colunas (esperado {N_COLS})")
        contratante = _s(row[2])
        if contratante is None:
            raise Ap013cParseError(f"linha {i}: contratante (col3) vazio")
        contratantes.add(contratante)
        registros.append(Ap013cRedistribuicao(
            linha=i,
            data_redistribuicao=_date(row[0]),
            referencia_externa=_s(row[1]),
            contratante_doc=contratante,
            participante_doc=_s(row[3]),
            carteira=_s(row[4]),
            valor_minimo_a_manter=_dec(row[5]),
            valor_suficiencia_antes=_dec(row[6]),
            qtd_ur_constituidas_antes=_int(row[7]),
            qtd_ur_a_constituir_antes=_int(row[8]),
            valor_constituido_efeitos_antes=_dec(row[9]),
            valor_livre_agenda_antes=_dec(row[10]),
            qtd_ur_constituidas_solicitadas=_int(row[11]),
            qtd_ur_a_constituir_solicitadas=_int(row[12]),
            valor_suficiencia_depois=_dec(row[13]),
            qtd_ur_constituidas_depois=_int(row[14]),
            qtd_ur_a_constituir_depois=_int(row[15]),
            valor_constituido_efeitos_depois=_dec(row[16]),
            valor_agenda_anomala=_dec(row[17]),
            observacoes=_s(row[18]),
        ))
    if not registros:
        raise Ap013cParseError("arquivo sem registros de redistribuição")
    return Ap013cParseResult(
        sha256=sha, data_referencia=_data_ref(original_filename, fallback_date),
        registros=registros, contratantes=contratantes,
    )
