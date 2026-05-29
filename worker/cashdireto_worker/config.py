"""Configuração do worker lida exclusivamente de variáveis de ambiente.

Regra do projeto: segredos só em env (nunca commitados). Ver .env.example.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

# Variáveis obrigatórias para o worker subir.
REQUIRED = ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "DATABASE_URL")


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    supabase_service_role_key: str          # service_role (BYPASSRLS) — só no worker, nunca no front
    database_url: str                        # Postgres direto (migrations/teste de RLS)
    storage_bucket: str = "fontes"
    llm_providers_path: str = "llm/providers.yaml"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        env = os.environ if env is None else env
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
