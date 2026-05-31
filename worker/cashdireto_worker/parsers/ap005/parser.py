"""Parser da fonte AP005 (todo o "a receber" do cliente — agenda de Unidades de Recebível).

Puro: não toca em banco. Layout oficial CERC em docs/fontes/AP005.md (nada inferido).
CSV sem cabeçalho, separador ';', 16 colunas. A coluna 12 é QUOTADA e contém uma lista de
sub-registros (separados por '|', cada um com 16 posições 12.1–12.16; a 12.16 pode faltar → 15).
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import date

from .._cerc import CercParseError, Fields, clean as _s, data_referencia as _data_ref, sha256_hex, to_text

N_COLS = 16
N_SUB = 16


class Ap005ParseError(CercParseError):
    """Erro de parsing do AP005 (nº de colunas/sub-campos inesperado, valor inválido)."""


_f = Fields(Ap005ParseError)
_dec = _f.dec
_date = _f.date


@dataclass(frozen=True)
class Ap005Pagamento:
    ordem: int
    titular_domicilio_doc: str | None
    tipo_conta: str | None
    compe: str | None
    ispb: str | None
    agencia: str | None
    conta: str | None
    valor_a_pagar: float | None
    beneficiario_doc: str | None
    data_liquidacao_efetiva: date | None
    valor_liquidacao_efetiva: float | None
    regra_divisao: str | None
    valor_onerado: float | None
    tipo_informacao_pagamento: str | None
    indicador_ordem_efeito: str | None
    valor_constituido_efeito: float | None
    identificador_cerc_contrato: str | None


@dataclass(frozen=True)
class Ap005Ur:
    linha: int
    referencia_externa: str | None
    registradora_doc: str | None
    credenciadora_doc: str | None
    usuario_final_doc: str
    arranjo: str | None
    data_liquidacao: date | None
    titular_ur_doc: str | None
    constituicao: str | None
    valor_constituido_total: float | None
    valor_constituido_antecip: float | None
    valor_bloqueado: float | None
    carteira: str | None
    valor_livre: float | None
    valor_total_ur: float | None
    atualizado_em: str | None
    pagamentos: list = field(default_factory=list)


@dataclass
class Ap005ParseResult:
    sha256: str
    data_referencia: date
    urs: list
    usuarios_finais: set
    total_pagamentos: int


def _pagamentos(compound: str) -> list:
    comp = _s(compound)
    if comp is None:
        return []
    pags = []
    for ordem, sub in enumerate(comp.split("|"), start=1):
        campos = sub.split(";")
        if len(campos) > N_SUB:
            raise Ap005ParseError(f"sub-registro com {len(campos)} campos (>16): {sub[:80]!r}")
        campos += [None] * (N_SUB - len(campos))  # 12.16 (e/ou outros finais) podem faltar
        pags.append(Ap005Pagamento(
            ordem=ordem,
            titular_domicilio_doc=_s(campos[0]),
            tipo_conta=_s(campos[1]),
            compe=_s(campos[2]),
            ispb=_s(campos[3]),
            agencia=_s(campos[4]),
            conta=_s(campos[5]),
            valor_a_pagar=_dec(campos[6]),
            beneficiario_doc=_s(campos[7]),
            data_liquidacao_efetiva=_date(campos[8]),
            valor_liquidacao_efetiva=_dec(campos[9]),
            regra_divisao=_s(campos[10]),
            valor_onerado=_dec(campos[11]),
            tipo_informacao_pagamento=_s(campos[12]),
            indicador_ordem_efeito=_s(campos[13]),
            valor_constituido_efeito=_dec(campos[14]),
            identificador_cerc_contrato=_s(campos[15]),
        ))
    return pags


def parse(content: str | bytes, *, original_filename: str | None, fallback_date: date) -> Ap005ParseResult:
    raw, text = to_text(content)
    sha = sha256_hex(raw)

    reader = csv.reader(io.StringIO(text), delimiter=";")
    urs = []
    usuarios = set()
    total_pag = 0
    for i, row in enumerate(reader, start=1):
        if not row or (len(row) == 1 and not row[0].strip()):
            continue  # linha vazia
        if len(row) != N_COLS:
            raise Ap005ParseError(f"linha {i}: {len(row)} colunas (esperado {N_COLS})")
        usuario = _s(row[3])
        if usuario is None:
            raise Ap005ParseError(f"linha {i}: usuário final recebedor (col4) vazio")
        pags = _pagamentos(row[11])
        total_pag += len(pags)
        usuarios.add(usuario)
        urs.append(Ap005Ur(
            linha=i,
            referencia_externa=_s(row[0]),
            registradora_doc=_s(row[1]),
            credenciadora_doc=_s(row[2]),
            usuario_final_doc=usuario,
            arranjo=_s(row[4]),
            data_liquidacao=_date(row[5]),
            titular_ur_doc=_s(row[6]),
            constituicao=_s(row[7]),
            valor_constituido_total=_dec(row[8]),
            valor_constituido_antecip=_dec(row[9]),
            valor_bloqueado=_dec(row[10]),
            carteira=_s(row[12]),
            valor_livre=_dec(row[13]),
            valor_total_ur=_dec(row[14]),
            atualizado_em=_s(row[15]),
            pagamentos=pags,
        ))
    if not urs:
        raise Ap005ParseError("arquivo sem registros de UR")
    return Ap005ParseResult(
        sha256=sha, data_referencia=_data_ref(original_filename, fallback_date),
        urs=urs, usuarios_finais=usuarios, total_pagamentos=total_pag,
    )
