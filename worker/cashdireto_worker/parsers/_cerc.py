"""Utilitários compartilhados dos parsers da família AP* da CERC.

Centraliza o que era duplicado em cada parser (AP005/AP007/AP013/AP013A/AP013B/AP013C):
leitura/sha do conteúdo, limpeza de string, conversões de campo (decimal/inteiro/data) e a
extração de data_referencia pelo token do nome do arquivo.

Os parsers RADAR e RAIOX **não** usam este módulo de propósito: o RADAR tem regra própria de
data (exige token de data único, devolve a origem) e o RAIOX é HTML — seus helpers divergem.

Cada fonte mantém sua exceção específica (ex.: Ap005ParseError) como subclasse de CercParseError;
os conversores de campo são expostos por `Fields(error)`, que levanta a exceção daquela fonte —
assim os testes `pytest.raises(Ap0XXParseError, ...)` continuam valendo.
"""
from __future__ import annotations

import hashlib
import re
from datetime import date

# Token de exatamente 8 dígitos no nome (o nome CERC tem id + data; só data válida vale).
_TOKEN_RE = re.compile(r"(?<!\d)(\d{8})(?!\d)")


class CercParseError(ValueError):
    """Erro de parsing de uma fonte CERC (base das exceções específicas por fonte)."""


def to_text(content: str | bytes) -> tuple[bytes, str]:
    """content (bytes|str) → (bytes crus para sha, texto decodificado utf-8-sig, tolera BOM)."""
    raw = content if isinstance(content, bytes) else content.encode("utf-8")
    return raw, raw.decode("utf-8-sig", "ignore")


def sha256_hex(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def clean(v: str | None) -> str | None:
    """Strip; devolve None se vazio (o antigo _s)."""
    if v is None:
        return None
    v = v.strip()
    return v or None


def data_referencia(filename: str | None, fallback: date) -> date:
    """data_referencia pelo token _YYYYMMDD_ do nome (primeiro válido em [2000,2100]); senão fallback."""
    for tok in _TOKEN_RE.findall(filename or ""):
        try:
            y, m, d = int(tok[:4]), int(tok[4:6]), int(tok[6:8])
            if 2000 <= y <= 2100:
                return date(y, m, d)
        except ValueError:
            pass
    return fallback


class Fields:
    """Conversores de campo que levantam a exceção específica da fonte (passada no construtor)."""

    def __init__(self, error: type[Exception]):
        self._error = error

    def dec(self, v: str | None) -> float | None:
        v = clean(v)
        if v is None:
            return None
        if "," in v and "." not in v:
            v = v.replace(",", ".")
        try:
            return float(v)
        except ValueError as exc:
            raise self._error(f"valor decimal inválido: {v!r}") from exc

    def intval(self, v: str | None) -> int | None:
        v = clean(v)
        if v is None:
            return None
        try:
            return int(v) if "." not in v else int(float(v))
        except ValueError as exc:
            raise self._error(f"valor inteiro inválido: {v!r}") from exc

    def date(self, v: str | None) -> date | None:
        v = clean(v)
        if v is None:
            return None
        try:
            return date.fromisoformat(v[:10])
        except ValueError as exc:
            raise self._error(f"data inválida: {v!r}") from exc
