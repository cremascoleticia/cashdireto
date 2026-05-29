# Cockpit de Recebíveis de Cartão

Produto de capital de giro lastreado em recebíveis de cartão. Lê arquivos da registradora (CERC),
calcula indicadores de crédito/monitoramento **de forma determinística** e entrega um dashboard
e um memorando narrado por LLM.

> Regras invioláveis, modelo de dados e plano de fases: ver [`CLAUDE.md`](CLAUDE.md) e
> [`docs/cockpit-recebiveis-cartao_SPEC.md`](docs/cockpit-recebiveis-cartao_SPEC.md).
> **A LLM nunca calcula indicador. Nenhum parser sem ficha de dicionário. Nada é inferido.**

## Stack

Supabase (Postgres + Storage + Auth/RLS) · Worker de ingestão em **Python** · Next.js (Railway) ·
camada LLM provider-agnóstica. Migrations versionadas via **Supabase CLI**.

## Estrutura

```
supabase/
  config.toml              # config do CLI (schema core exposto à API)
  migrations/              # SQL versionado (sobe do zero)
    20260529000001_core_schema.sql
    20260529000002_core_rls.sql
    20260529000003_storage.sql
  tests/rls_cross_titular.sql   # critério de aceite da Fase 0
scripts/run_rls_test.py    # runner do teste de RLS (lê DATABASE_URL)
worker/                    # worker de ingestão (Python) — scaffold na Fase 0
docs/fontes/               # fichas de dicionário (uma por fonte; sem ficha = PENDENTE_DICIONARIO)
samples/                   # amostras reais (NÃO versionadas)
.github/workflows/ci.yml   # pytest + migrations do zero + teste de RLS
```

## Status — Fase 0 (Fundação)

Schema `core` (identidade, ingestão bruta, canônico-alvo, derivado), RLS multi-titular em todas as
tabelas, Storage privado, scaffold do worker e CI. Fases 1a+ ficam bloqueadas até a entrega de
amostra + dicionário + ficha de cada fonte.

## Setup

```bash
cp .env.example .env        # preencher SUPABASE_*, DATABASE_URL
```

### Aplicar migrations

- **Projeto remoto (sem Docker):**
  ```bash
  npx supabase link --project-ref <ref>
  npx supabase db push
  ```
- **Stack local (requer Docker):**
  ```bash
  npx supabase start
  npx supabase db reset      # aplica todas as migrations do zero
  ```

### Rodar o teste de aceite da Fase 0 (RLS cross-titular)

```bash
# DATABASE_URL apontando para um Postgres do Supabase (remoto ou local)
python scripts/run_rls_test.py
# ou:  psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f supabase/tests/rls_cross_titular.sql
```

No CI (`.github/workflows/ci.yml`) isso roda automaticamente contra `supabase/postgres`.

### Worker

```bash
cd worker && pip install -e ".[dev]" && pytest -q
```
