#!/usr/bin/env python
"""Roda o teste de RLS cross-titular (supabase/tests/rls_cross_titular.sql).

Uso:
    DATABASE_URL=postgres://...  python scripts/run_rls_test.py

DATABASE_URL deve apontar para um Postgres do Supabase (projeto remoto linkado ou stack
local). O .sql faz seed, valida o isolamento e dá ROLLBACK — não deixa resíduo.

Sucesso = sai com código 0 e imprime a NOTICE "RLS cross-titular: OK".
Qualquer violação de isolamento vira exceção no banco e derruba o teste (código != 0).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

SQL_FILE = Path(__file__).resolve().parent.parent / "supabase" / "tests" / "rls_cross_titular.sql"


def _connect(dsn: str):
    """Conecta com psycopg (v3) ou psycopg2, o que estiver disponível."""
    try:
        import psycopg  # type: ignore

        return ("psycopg3", psycopg.connect(dsn, autocommit=True))
    except ImportError:
        pass
    try:
        import psycopg2  # type: ignore

        conn = psycopg2.connect(dsn)
        conn.autocommit = True
        return ("psycopg2", conn)
    except ImportError:
        sys.exit(
            "ERRO: nenhum driver Postgres encontrado.\n"
            "Instale um:  pip install 'psycopg[binary]'   (ou)  pip install psycopg2-binary"
        )


def main() -> int:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        sys.exit("ERRO: defina DATABASE_URL (Postgres do Supabase) no ambiente.")

    sql = SQL_FILE.read_text(encoding="utf-8")
    driver, conn = _connect(dsn)
    print(f"[run_rls_test] driver={driver}  alvo={dsn.split('@')[-1]}")

    try:
        if driver == "psycopg3":
            # O script tem vários comandos; o protocolo estendido do psycopg3 não aceita isso.
            # Usamos o protocolo simples do libpq (PQexec), que executa o batch inteiro.
            from psycopg import pq

            res = conn.pgconn.exec_(sql.encode("utf-8"))
            if res.status in (pq.ExecStatus.FATAL_ERROR, pq.ExecStatus.NONFATAL_ERROR):
                raise RuntimeError(res.error_message.decode("utf-8", "replace").strip())
        else:
            # psycopg2 usa o protocolo simples — aceita múltiplos comandos num execute().
            with conn.cursor() as cur:
                cur.execute(sql)
            for n in getattr(conn, "notices", []) or []:
                print("  " + str(n).strip())
        # Ausência de exceção = todas as asserções do .sql passaram.
        print("[run_rls_test] PASS — RLS bloqueia acesso cross-titular.")
        return 0
    except Exception as exc:  # noqa: BLE001 — queremos qualquer erro do banco como falha
        print(f"[run_rls_test] FAIL — {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
