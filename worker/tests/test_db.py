"""Testes do parser de DATABASE_URL → conninfo libpq (db.conninfo_from_url).

Foco: senha com `@`/`:` literais (caso real do Postgres do Supabase), que
quebra `psycopg.connect(url)` se a URL for parseada inteira.
"""
from psycopg.conninfo import conninfo_to_dict

from cashdireto_worker.db import conninfo_from_url


def _d(url):
    return conninfo_to_dict(conninfo_from_url(url))


def test_senha_com_arroba_e_dois_pontos():
    d = _d("postgresql://postgres:p@ss:w0rd@@db.host.co:5432/postgres")
    assert d["user"] == "postgres"
    assert d["password"] == "p@ss:w0rd@"      # tudo entre o 1º ':' e o ÚLTIMO '@'
    assert d["host"] == "db.host.co"
    assert d["port"] == "5432"
    assert d["dbname"] == "postgres"


def test_usuario_pooler_com_ponto():
    d = _d("postgresql://postgres.abcdef:senha@aws-0-sa-east-1.pooler.supabase.com:6543/postgres")
    assert d["user"] == "postgres.abcdef"
    assert d["host"] == "aws-0-sa-east-1.pooler.supabase.com"
    assert d["port"] == "6543"


def test_query_params_viram_kwargs():
    d = _d("postgresql://u:p@h:5432/db?sslmode=require")
    assert d["sslmode"] == "require"


def test_string_que_nao_e_url_passa_intacta():
    # já é conninfo libpq → devolve como veio
    conn = "host=localhost port=5432 dbname=test"
    assert conninfo_from_url(conn) == conn
