"""Orquestrador de ingestão — liga upload → parser → loader (carga no banco).

Recebe um arquivo (nome + conteúdo), descobre a fonte pelo nome, chama o parser e o loader
corretos. É a engrenagem que a página de upload do dashboard aciona. A detecção do tipo é pura
e testável; a carga (carregar) executa numa conexão psycopg (casca fina, como os loaders).

Nomenclatura CERC: `CERC-<TIPO>_<raizCNPJ>_<YYYYMMDD>_<seq>_ret.csv` (ex.: CERC-AP013C_...).
RADAR/RAIOX vêm com o nome da fonte no arquivo (RADAR.csv / RAIOX.html).
"""
from __future__ import annotations

from datetime import date

from .parsers import ap005, ap007, ap013, ap013a, ap013b, ap013c, radar, raiox
from .parsers.radar import loader as radar_loader
from .parsers.raiox import loader as raiox_loader


class IngestError(ValueError):
    """Não foi possível reconhecer a fonte do arquivo, ou falhou ao processar."""


# tipo → (função de parse, função de carga). Todos os parse() têm a mesma assinatura
# (content, *, original_filename, fallback_date) e devolvem um ParseResult com .sha256/.data_referencia.
# Todos os carregar() têm assinatura (conn, res, *, nome_original).
REGISTRO = {
    "RADAR":  (radar.parse,  radar_loader.carregar),
    "RAIOX":  (raiox.parse,  raiox_loader.carregar),
    "AP005":  (ap005.parse,  ap005.loader.carregar),
    "AP007":  (ap007.parse,  ap007.loader.carregar),
    "AP013":  (ap013.parse,  ap013.loader.carregar),
    "AP013A": (ap013a.parse, ap013a.loader.carregar),
    "AP013B": (ap013b.parse, ap013b.loader.carregar),
    "AP013C": (ap013c.parse, ap013c.loader.carregar),
}


def detectar_tipo(nome_arquivo: str | None) -> str:
    """Descobre a fonte pelo nome do arquivo. Levanta IngestError se não reconhecer."""
    up = (nome_arquivo or "").upper()
    if "CERC-" in up:
        resto = up.split("CERC-", 1)[1]
        token = resto.split("_", 1)[0].split(".", 1)[0]   # ex.: AP013C, AP013, AP005
        if token in REGISTRO:
            return token
        raise IngestError(f"tipo CERC não reconhecido: {token!r} (arquivo {nome_arquivo!r})")
    if "RAIOX" in up or up.endswith((".HTML", ".HTM")):
        return "RAIOX"
    if "RADAR" in up:
        return "RADAR"
    raise IngestError(f"não reconheci a fonte do arquivo: {nome_arquivo!r}")


def processar_arquivo(conn, nome_arquivo: str, conteudo: str | bytes, *,
                      fallback_date: date) -> dict:
    """Detecta a fonte, faz o parse e carrega no banco. Devolve um resumo do processamento."""
    tipo = detectar_tipo(nome_arquivo)
    parse, carregar = REGISTRO[tipo]
    res = parse(conteudo, original_filename=nome_arquivo, fallback_date=fallback_date)
    carregar(conn, res, nome_original=nome_arquivo)
    return {
        "tipo": tipo,
        "nome_arquivo": nome_arquivo,
        "sha256": res.sha256,
        "data_referencia": res.data_referencia,
    }
