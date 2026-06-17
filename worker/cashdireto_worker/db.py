"""Conexão com o Postgres do Supabase (psycopg3), lida de DATABASE_URL.

Usa a conexão direta (service_role / postgres) — ignora RLS, só no servidor, nunca no front.
"""
from __future__ import annotations

from .config import Settings


def conninfo_from_url(url: str) -> str:
    """Converte a DATABASE_URL em conninfo libpq, robusto a `@`/`:` na senha.

    A senha do Postgres do Supabase contém `@` literal; `psycopg.connect(url)`
    parseia a URL e quebra (o `@` é lido como separador de host). Aqui separamos
    os componentes à mão — userinfo pelo ÚLTIMO `@` (o host não tem `@`) — e
    deixamos o `make_conninfo` escapar cada campo. Se a string não parecer uma
    URL, devolvemos como veio (já é conninfo libpq).
    """
    from urllib.parse import unquote

    from psycopg.conninfo import make_conninfo

    scheme, sep, rest = url.partition("://")
    if not sep or scheme.lower() not in ("postgres", "postgresql"):
        return url
    userinfo, at, hostinfo = rest.rpartition("@")
    if not at:
        return url
    user, _, password = userinfo.partition(":")
    hostport, _, pathq = hostinfo.partition("/")
    dbname, _, query = pathq.partition("?")
    host, _, port = hostport.partition(":")

    kwargs: dict[str, str] = {}
    if host:
        kwargs["host"] = host
    if port:
        kwargs["port"] = port
    if user:
        kwargs["user"] = unquote(user)
    if password:
        # Senha crua do .env: NÃO decodificar (o `@` é literal, não %40).
        kwargs["password"] = password
    if dbname:
        kwargs["dbname"] = unquote(dbname)
    for pair in query.split("&") if query else []:
        if "=" in pair:
            k, _, v = pair.partition("=")
            kwargs[k] = unquote(v)
    return make_conninfo(**kwargs)


def conectar(settings: Settings | None = None):
    import psycopg  # import tardio: o pacote não exige psycopg para os testes puros
    s = settings or Settings.from_env()
    return psycopg.connect(conninfo_from_url(s.database_url))
