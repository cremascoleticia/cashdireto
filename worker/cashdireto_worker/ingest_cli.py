"""CLI de ingestão — usado pela página de upload do portal (Next.js chama via subprocess).

Uso: python -m cashdireto_worker.ingest_cli <caminho_do_arquivo> [nome_original]

Lê o arquivo, detecta a fonte, parseia, carrega no banco (mesma transação) e imprime um JSON
com o resultado em stdout. Erros saem como JSON {"erro": ...} com exit code 1. Reaproveita
ingest.processar_arquivo e db.conectar (nada novo de lógica aqui — só a casca de linha de comando).
"""
from __future__ import annotations

import json
import sys
from datetime import date

from .db import conectar
from .ingest import processar_arquivo


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(json.dumps({"erro": "uso: ingest_cli <arquivo> [nome_original]"}))
        return 1
    caminho = argv[1]
    nome = argv[2] if len(argv) > 2 else caminho.replace("\\", "/").rsplit("/", 1)[-1]
    try:
        with open(caminho, "rb") as f:
            conteudo = f.read()
    except OSError as exc:
        print(json.dumps({"erro": f"não consegui ler o arquivo: {exc}"}))
        return 1

    conn = conectar()
    try:
        res = processar_arquivo(conn, nome, conteudo, fallback_date=date.today())
        conn.commit()
    except Exception as exc:  # noqa: BLE001 — devolve o erro pro front
        conn.rollback()
        print(json.dumps({"erro": f"{type(exc).__name__}: {exc}", "nome_arquivo": nome}))
        return 1
    finally:
        conn.close()

    print(json.dumps({
        "ok": True,
        "tipo": res["tipo"],
        "nome_arquivo": res["nome_arquivo"],
        "sha256": res["sha256"],
        "data_referencia": str(res["data_referencia"]),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
