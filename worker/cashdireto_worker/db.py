"""Conexão com o Postgres do Supabase (psycopg3), lida de DATABASE_URL.

Usa a conexão direta (service_role / postgres) — ignora RLS, só no servidor, nunca no front.
"""
from __future__ import annotations

from .config import Settings


def conectar(settings: Settings | None = None):
    import psycopg  # import tardio: o pacote não exige psycopg para os testes puros
    s = settings or Settings.from_env()
    return psycopg.connect(s.database_url)
