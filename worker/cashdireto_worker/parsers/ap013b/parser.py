"""Parser da fonte AP013B — situação do contrato com quebra por credenciadora alcançada.

Puro: não toca em banco. Campos vêm do dicionário oficial CERC (docs/fontes/AP013B.md).
⚠️ Layout FÍSICO assumido = padrão AP005/AP007/AP013 (CSV ';' sem cabeçalho, 17 colunas; col.16
quotada contém lista). Confirmar com amostra real — ver suposições na ficha.

- col.16 = informações por credenciadora (sub-registros '|'; cada um com 10 posições ';',
  todas escalares → sem ambiguidade de aninhamento).
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import date

from .._cerc import CercParseError, Fields, clean as _s, data_referencia as _data_ref, sha256_hex, to_text

N_COLS = 17
N_SUB_CRED = 10


class Ap013bParseError(CercParseError):
    """Erro de parsing do AP013B (nº de colunas/sub-campos inesperado, valor inválido)."""


_f = Fields(Ap013bParseError)
_dec = _f.dec
_int = _f.intval
_date = _f.date


@dataclass(frozen=True)
class Ap013bCredenciadora:
    ordem: int
    entidade_registradora_doc: str | None
    credenciadora_doc: str | None
    qtd_ur_constituidas: int | None
    qtd_ur_nao_constituidas: int | None
    qtd_efeitos: int | None
    valor_efeitos_solicitados: float | None
    valor_efeitos_calculados_cerc: float | None
    valor_efeitos_calculados_credenciadoras: float | None
    qtd_ur_prioridade_1: int | None
    qtd_ur_prioridade_diferente_1: int | None


@dataclass(frozen=True)
class Ap013bContrato:
    linha: int
    referencia_externa: str | None
    identificador_contrato: str | None
    contratante_doc: str
    repactuacao: str | None
    identificador_contrato_anterior: str | None
    participante_doc: str | None
    detentor_doc: str | None
    carteira: str | None
    tipo_servico: str | None
    tipo_efeito: str | None
    saldo_devedor: float | None
    data_criacao: date | None
    data_assinatura: date | None
    data_vencimento: date | None
    data_ultima_atualizacao: date | None
    indicador_sobrecolateralizacao: float | None
    credenciadoras: list = field(default_factory=list)


@dataclass
class Ap013bParseResult:
    sha256: str
    data_referencia: date
    contratos: list
    contratantes: set
    total_credenciadoras: int


def _credenciadoras(compound: str | None) -> list:
    """col.16 — sub-registros '|'; cada um com 10 posições ';' (faltando finais → NULL)."""
    comp = _s(compound)
    if comp is None:
        return []
    creds = []
    for ordem, sub in enumerate(comp.split("|"), start=1):
        if not sub.strip():
            continue
        campos = sub.split(";")
        if len(campos) > N_SUB_CRED:
            raise Ap013bParseError(f"credenciadora com {len(campos)} campos (>10): {sub[:80]!r}")
        campos += [None] * (N_SUB_CRED - len(campos))
        creds.append(Ap013bCredenciadora(
            ordem=ordem,
            entidade_registradora_doc=_s(campos[0]),
            credenciadora_doc=_s(campos[1]),
            qtd_ur_constituidas=_int(campos[2]),
            qtd_ur_nao_constituidas=_int(campos[3]),
            qtd_efeitos=_int(campos[4]),
            valor_efeitos_solicitados=_dec(campos[5]),
            valor_efeitos_calculados_cerc=_dec(campos[6]),
            valor_efeitos_calculados_credenciadoras=_dec(campos[7]),
            qtd_ur_prioridade_1=_int(campos[8]),
            qtd_ur_prioridade_diferente_1=_int(campos[9]),
        ))
    return creds


def parse(content: str | bytes, *, original_filename: str | None, fallback_date: date) -> Ap013bParseResult:
    raw, text = to_text(content)
    sha = sha256_hex(raw)

    reader = csv.reader(io.StringIO(text), delimiter=";")
    contratos = []
    contratantes = set()
    total_cred = 0
    for i, row in enumerate(reader, start=1):
        if not row or (len(row) == 1 and not row[0].strip()):
            continue  # linha vazia
        if len(row) != N_COLS:
            raise Ap013bParseError(f"linha {i}: {len(row)} colunas (esperado {N_COLS})")
        contratante = _s(row[2])
        if contratante is None:
            raise Ap013bParseError(f"linha {i}: contratante (col3) vazio")
        creds = _credenciadoras(row[15])
        total_cred += len(creds)
        contratantes.add(contratante)
        contratos.append(Ap013bContrato(
            linha=i,
            referencia_externa=_s(row[0]),
            identificador_contrato=_s(row[1]),
            contratante_doc=contratante,
            repactuacao=_s(row[3]),
            identificador_contrato_anterior=_s(row[4]),
            participante_doc=_s(row[5]),
            detentor_doc=_s(row[6]),
            carteira=_s(row[7]),
            tipo_servico=_s(row[8]),
            tipo_efeito=_s(row[9]),
            saldo_devedor=_dec(row[10]),
            data_criacao=_date(row[11]),
            data_assinatura=_date(row[12]),
            data_vencimento=_date(row[13]),
            data_ultima_atualizacao=_date(row[14]),
            indicador_sobrecolateralizacao=_dec(row[16]),
            credenciadoras=creds,
        ))
    if not contratos:
        raise Ap013bParseError("arquivo sem registros de contrato")
    return Ap013bParseResult(
        sha256=sha, data_referencia=_data_ref(original_filename, fallback_date),
        contratos=contratos, contratantes=contratantes, total_credenciadoras=total_cred,
    )
