"""Parser da fonte RADAR (agenda futura de recebíveis) — bruto → canônico (tidy).

Puro: não toca em banco. Lê o CSV, valida o cabeçalho, faz o UNPIVOT das 20 colunas de valor
(5 janelas × 4 situações) em registros tidy e devolve metadados. Layout vem de docs/fontes/RADAR.md;
nada é inferido — cabeçalho diferente do esperado é erro, não palpite.
"""
from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import dataclass
from datetime import date

SITUACOES = ("livre", "pre", "comprometido", "constituido")
JANELAS = ("0_30", "31_60", "61_90", "91_120", "120_mais")

ID_COLS = (
    "documento_estabelecimento_comercial",
    "documento_credenciadora_sub",
    "razao_social_credenciadora",
    "arranjo",
)
VALUE_COLS = tuple(f"valor_{s}_{j}" for s in SITUACOES for j in JANELAS)
EXPECTED_HEADER = list(ID_COLS) + list(VALUE_COLS)

# Tokens de exatamente 8 dígitos no nome (o nome CERC tem mais de um, ex.: id + data).
_TOKEN_RE = re.compile(r"(?<!\d)(\d{8})(?!\d)")


class RadarParseError(ValueError):
    """Erro de parsing do RADAR: arquivo vazio, cabeçalho inesperado ou linha malformada."""


@dataclass(frozen=True)
class AgendaRegistro:
    estabelecimento_cnpj: str
    credenciadora_doc: str
    credenciadora_nome: str
    arranjo: str
    janela: str
    situacao: str
    valor: float


@dataclass
class RadarParseResult:
    data_referencia: date
    data_origem: str            # 'nome_arquivo' | 'fallback'
    sha256: str
    registros: list[AgendaRegistro]
    estabelecimentos: set[str]
    linhas_origem: int          # nº de linhas de dados (sem cabeçalho)


def _token_para_data(token: str) -> date | None:
    """Converte um token de 8 dígitos em data (YYYYMMDD), só se ano em [2000, 2100] e mês/dia válidos."""
    try:
        ano, mes, dia = int(token[:4]), int(token[4:6]), int(token[6:8])
        if 2000 <= ano <= 2100:
            return date(ano, mes, dia)
    except ValueError:
        pass
    return None


def extrair_data_referencia(filename: str | None, fallback: date) -> tuple[date, str]:
    """Data de referência a partir do nome (token YYYYMMDD).

    O nome CERC tem mais de um token de 8 dígitos (ex.: id + data), então só aceitamos o que
    é data válida. Exatamente uma data válida → usa o nome; zero ou múltiplas (ambíguo) →
    fallback para a data da análise. Não adivinha.
    """
    datas: list[date] = []
    for token in _TOKEN_RE.findall(filename or ""):
        dt = _token_para_data(token)
        if dt is not None and dt not in datas:
            datas.append(dt)
    if len(datas) == 1:
        return datas[0], "nome_arquivo"
    return fallback, "fallback"


def _to_text(content: str | bytes) -> tuple[str, bytes]:
    if isinstance(content, str):
        return content, content.encode("utf-8")
    return content.decode("utf-8-sig"), content  # utf-8-sig tolera BOM


def parse(content: str | bytes, *, original_filename: str | None, fallback_date: date) -> RadarParseResult:
    text, raw_bytes = _to_text(content)
    sha = hashlib.sha256(raw_bytes).hexdigest()

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise RadarParseError("arquivo vazio")
    if reader.fieldnames != EXPECTED_HEADER:
        veio = list(reader.fieldnames)
        faltando = [c for c in EXPECTED_HEADER if c not in veio]
        extras = [c for c in veio if c not in EXPECTED_HEADER]
        raise RadarParseError(
            f"cabeçalho inesperado (esperado {len(EXPECTED_HEADER)} colunas, veio {len(veio)}); "
            f"faltando={faltando} extras={extras}"
        )

    data_ref, origem = extrair_data_referencia(original_filename, fallback_date)

    registros: list[AgendaRegistro] = []
    linhas_origem = 0
    for i, rec in enumerate(reader, start=2):  # linha 1 = cabeçalho; dados começam na linha 2
        linhas_origem += 1
        # DictReader: campo a mais cai na chave None; campo a menos vira valor None.
        if None in rec or any(rec.get(c) is None for c in EXPECTED_HEADER):
            raise RadarParseError(f"linha {i}: número de campos diferente do cabeçalho")

        estab = rec["documento_estabelecimento_comercial"].strip()
        cred_doc = rec["documento_credenciadora_sub"].strip()
        cred_nome = rec["razao_social_credenciadora"].strip()
        arranjo = rec["arranjo"].strip()
        if not estab or not arranjo:
            raise RadarParseError(f"linha {i}: estabelecimento e/ou arranjo vazio")

        for s in SITUACOES:
            for j in JANELAS:
                col = f"valor_{s}_{j}"
                bruto = rec[col].strip()
                try:
                    valor = float(bruto) if bruto else 0.0
                except ValueError as exc:
                    raise RadarParseError(f"linha {i} coluna {col}: valor não numérico '{bruto}'") from exc
                if valor < 0:
                    raise RadarParseError(f"linha {i} coluna {col}: valor negativo {valor}")
                registros.append(
                    AgendaRegistro(estab, cred_doc, cred_nome, arranjo, j, s, valor)
                )

    return RadarParseResult(
        data_referencia=data_ref,
        data_origem=origem,
        sha256=sha,
        registros=registros,
        estabelecimentos={x.estabelecimento_cnpj for x in registros},
        linhas_origem=linhas_origem,
    )
