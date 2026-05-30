"""Parser da fonte AP013C — resultado da redistribuição do Gestão de Colateral (antes x depois).

Puro: não toca em banco. Campos vêm do dicionário oficial CERC (docs/fontes/AP013C.md).
⚠️ Layout FÍSICO assumido = padrão das demais fontes CERC (CSV ';' sem cabeçalho, 19 colunas
escalares, sem listas). Confirmar com amostra real — ver suposições na ficha.

1 linha = 1 contrato. Tem Contratante (col3) → titular (multi-titular).
"""
from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import dataclass
from datetime import date

N_COLS = 19
_TOKEN_RE = re.compile(r"(?<!\d)(\d{8})(?!\d)")


class Ap013cParseError(ValueError):
    """Erro de parsing do AP013C (nº de colunas inesperado, valor inválido)."""


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


def _s(v: str | None) -> str | None:
    if v is None:
        return None
    v = v.strip()
    return v or None


def _dec(v: str | None) -> float | None:
    v = _s(v)
    if v is None:
        return None
    if "," in v and "." not in v:
        v = v.replace(",", ".")
    try:
        return float(v)
    except ValueError as exc:
        raise Ap013cParseError(f"valor decimal inválido: {v!r}") from exc


def _int(v: str | None) -> int | None:
    v = _s(v)
    if v is None:
        return None
    try:
        return int(v) if "." not in v else int(float(v))
    except ValueError as exc:
        raise Ap013cParseError(f"valor inteiro inválido: {v!r}") from exc


def _date(v: str | None) -> date | None:
    v = _s(v)
    if v is None:
        return None
    try:
        return date.fromisoformat(v[:10])
    except ValueError as exc:
        raise Ap013cParseError(f"data inválida: {v!r}") from exc


def _data_ref(filename: str | None, fallback: date) -> date:
    for tok in _TOKEN_RE.findall(filename or ""):
        try:
            y, m, d = int(tok[:4]), int(tok[4:6]), int(tok[6:8])
            if 2000 <= y <= 2100:
                return date(y, m, d)
        except ValueError:
            pass
    return fallback


def parse(content: str | bytes, *, original_filename: str | None, fallback_date: date) -> Ap013cParseResult:
    raw = content if isinstance(content, bytes) else content.encode("utf-8")
    sha = hashlib.sha256(raw).hexdigest()
    text = raw.decode("utf-8-sig", "ignore")

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
