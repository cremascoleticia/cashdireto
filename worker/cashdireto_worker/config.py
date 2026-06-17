"""Configuração do worker lida exclusivamente de variáveis de ambiente.

Regra do projeto: segredos só em env (nunca commitados). Ver .env.example.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

# Variáveis obrigatórias para o worker subir.
REQUIRED = ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "DATABASE_URL")


def _parse_dotenv(text: str) -> dict[str, str]:
    """Parse de .env mínimo (sem dependência): KEY=VALUE por linha.

    Ignora linhas vazias e comentários (#). Aceita um `export ` opcional no
    início. Divide só no primeiro `=` (valores podem conter `=`, `@`, `:`).
    Remove aspas simples/duplas que envolvam o valor inteiro.
    """
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        key, _, value = line.partition("=")
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        out[key] = value
    return out


def _find_dotenv(start: Path | None = None) -> Path | None:
    """Procura o `.env` do repo: de `start` até a raiz do repo (dir com `.git`).

    A busca é LIMITADA à raiz do repositório de propósito — subir até o root do
    disco pegaria um `.env` solto no home do usuário e carregaria segredos
    errados no worker. Sem `.git` em nenhum ancestral, só o próprio `start` é
    inspecionado (nunca os pais).
    """
    here = (start or Path.cwd()).resolve()
    chain = (here, *here.parents)
    repo_root = next((d for d in chain if (d / ".git").exists()), None)
    ceiling = repo_root if repo_root is not None else here
    for directory in chain:
        candidate = directory / ".env"
        if candidate.is_file():
            return candidate
        if directory == ceiling:
            break
    return None


def load_dotenv_into(env: dict[str, str], start: Path | None = None) -> dict[str, str]:
    """Mescla o `.env` encontrado em `env`, sem sobrescrever o que já existe.

    O ambiente real (os.environ ou o que o chamador já passou) tem precedência
    sobre o arquivo — o `.env` só preenche o que estiver faltando.
    """
    path = _find_dotenv(start)
    if path is None:
        return env
    file_vars = _parse_dotenv(path.read_text(encoding="utf-8"))
    for key, value in file_vars.items():
        env.setdefault(key, value)
    return env


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    supabase_service_role_key: str          # service_role (BYPASSRLS) — só no worker, nunca no front
    database_url: str                        # Postgres direto (migrations/teste de RLS)
    storage_bucket: str = "fontes"
    llm_providers_path: str = "llm/providers.yaml"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        # Quando ninguém passa env explícito, lemos o ambiente real e
        # completamos com o .env do repo (cwd + pais). Com env explícito
        # (testes), respeitamos exatamente o que foi passado — sem .env.
        if env is None:
            env = load_dotenv_into(dict(os.environ))
        missing = [k for k in REQUIRED if not env.get(k)]
        if missing:
            raise RuntimeError(
                "Variáveis de ambiente faltando: " + ", ".join(missing) + ". Ver .env.example."
            )
        return cls(
            supabase_url=env["SUPABASE_URL"],
            supabase_service_role_key=env["SUPABASE_SERVICE_ROLE_KEY"],
            database_url=env["DATABASE_URL"],
            storage_bucket=env.get("STORAGE_BUCKET", "fontes"),
            llm_providers_path=env.get("LLM_PROVIDERS_PATH", "llm/providers.yaml"),
        )
