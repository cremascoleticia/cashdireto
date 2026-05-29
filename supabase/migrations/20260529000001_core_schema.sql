-- 20260529000001_core_schema.sql
-- Fase 0 — Fundação. Cria o schema `core`:
--   • Identidade (titular + vínculo de acesso usuário↔titular)
--   • Ingestão BRUTA (fonte_arquivo) — fonte da verdade reprocessável, idempotente por sha256
--   • CANÔNICO (alvo) — APENAS o esqueleto estrutural (id/titular/fonte/data).
--     As colunas de CONTEÚDO NÃO são definidas aqui: entram na Fase 1, uma fonte por vez,
--     a partir da ficha de dicionário em docs/fontes/<TIPO>.md. Nada é inferido (regra de ouro).
--   • DERIVADO (indicador_snapshot, gatilho_evento, memorando) — controlado por nós.
-- RLS e grants ficam na migration 20260529000002. Storage em 20260529000003.

create schema if not exists core;

-- gen_random_uuid()
create extension if not exists pgcrypto;

-- ════════════════════════════ Identidade ════════════════════════════

create table core.titular (
  id           uuid primary key default gen_random_uuid(),
  cnpj         text,
  razao_social text,
  alias        text not null unique,            -- identificador SEM PII enviado à LLM (ex.: 'T-001')
  criado_em    timestamptz not null default now()
);
comment on table  core.titular        is 'Carteira multi-titular. `alias` é o rótulo sem PII usado nos payloads da LLM.';
comment on column core.titular.alias  is 'Apelido anônimo (ex.: T-001). Única coluna de identidade que pode ir à LLM.';

-- Mapeia quais usuários (auth.users) enxergam quais titulares. É a base do RLS multi-titular.
create table core.titular_membro (
  titular_id uuid not null references core.titular(id) on delete cascade,
  user_id    uuid not null references auth.users(id)   on delete cascade,
  papel      text not null default 'leitor' check (papel in ('leitor','editor','admin')),
  criado_em  timestamptz not null default now(),
  primary key (titular_id, user_id)
);
comment on table core.titular_membro is 'Vínculo usuário↔titular; controla a visibilidade de todas as linhas no RLS.';
create index titular_membro_user_idx on core.titular_membro (user_id);

-- ══════════════════════════ Ingestão BRUTA ══════════════════════════

create table core.fonte_arquivo (
  id              uuid primary key default gen_random_uuid(),
  titular_id      uuid not null references core.titular(id) on delete restrict,
  tipo            text not null
                    check (tipo in ('RADAR','RAIOX','AP005','AP007','AP013A','AP013B')),
  sha256          text not null,
  nome_original   text,
  data_referencia date,
  status          text not null default 'recebido'
                    check (status in ('recebido','parseado','validado','falha','PENDENTE_DICIONARIO')),
  payload_bruto   jsonb,
  erro            text,
  criado_em       timestamptz not null default now(),
  constraint fonte_arquivo_sha256_uniq unique (sha256)   -- idempotência: reprocessar não duplica
);
comment on table  core.fonte_arquivo        is 'Camada BRUTA reprocessável. unique(sha256) garante idempotência de ingestão.';
comment on column core.fonte_arquivo.tipo   is 'Fonte CERC. Só vira parser depois da ficha de dicionário (senão fica PENDENTE_DICIONARIO).';
comment on column core.fonte_arquivo.status is 'recebido|parseado|validado|falha|PENDENTE_DICIONARIO';
create index fonte_arquivo_titular_idx on core.fonte_arquivo (titular_id, tipo, data_referencia);

-- ════════════ CANÔNICO (ALVO — só esqueleto; conteúdo na Fase 1) ════════════
-- As colunas de conteúdo destas tabelas serão adicionadas por migrations da Fase 1,
-- fonte por fonte, conforme o dicionário. NÃO inferir layout aqui.

create table core.agenda_ur (
  id              uuid primary key default gen_random_uuid(),
  titular_id      uuid not null references core.titular(id)        on delete cascade,
  fonte_id        uuid not null references core.fonte_arquivo(id)  on delete cascade,
  data_referencia date,
  criado_em       timestamptz not null default now()
  -- + colunas de conteúdo na Fase 1 (dicionário da fonte de agenda de UR)
);
comment on table core.agenda_ur is 'CANÔNICO (alvo). Esqueleto; colunas de conteúdo definidas na Fase 1 via dicionário.';

create table core.contrato_efeito (
  id              uuid primary key default gen_random_uuid(),
  titular_id      uuid not null references core.titular(id)        on delete cascade,
  fonte_id        uuid not null references core.fonte_arquivo(id)  on delete cascade,
  data_referencia date,
  criado_em       timestamptz not null default now()
  -- + colunas de conteúdo na Fase 1
);
comment on table core.contrato_efeito is 'CANÔNICO (alvo). Esqueleto; colunas de conteúdo definidas na Fase 1 via dicionário.';

create table core.faturamento_tpv (
  id              uuid primary key default gen_random_uuid(),
  titular_id      uuid not null references core.titular(id)        on delete cascade,
  fonte_id        uuid not null references core.fonte_arquivo(id)  on delete cascade,
  criado_em       timestamptz not null default now()
  -- + colunas de conteúdo na Fase 1
);
comment on table core.faturamento_tpv is 'CANÔNICO (alvo). Esqueleto; colunas de conteúdo definidas na Fase 1 via dicionário.';

create table core.posicao_consolidada (
  id              uuid primary key default gen_random_uuid(),
  titular_id      uuid not null references core.titular(id)        on delete cascade,
  fonte_id        uuid not null references core.fonte_arquivo(id)  on delete cascade,
  data_referencia date,
  criado_em       timestamptz not null default now()
  -- + colunas de conteúdo na Fase 1
);
comment on table core.posicao_consolidada is 'CANÔNICO (alvo). Esqueleto; colunas de conteúdo definidas na Fase 1 via dicionário.';

-- ════════════════════════════ DERIVADO ════════════════════════════
-- Independe do layout das fontes; é calculado por nós (SQL/Python determinístico).

create table core.indicador_snapshot (
  id              uuid primary key default gen_random_uuid(),
  titular_id      uuid not null references core.titular(id) on delete cascade,
  indicador       text not null,
  valor           numeric,
  data_referencia date not null,
  detalhe         jsonb,
  criado_em       timestamptz not null default now()
);
comment on table core.indicador_snapshot is 'DERIVADO. Indicadores calculados por nós; a LLM nunca calcula — só narra.';
create index indicador_snapshot_lookup_idx
  on core.indicador_snapshot (titular_id, indicador, data_referencia);

create table core.gatilho_evento (
  id            uuid primary key default gen_random_uuid(),
  titular_id    uuid not null references core.titular(id) on delete cascade,
  gatilho       text not null,
  severidade    text not null default 'info' check (severidade in ('info','alerta','critico')),
  valor_aferido numeric,
  limite        numeric,
  disparado_em  timestamptz not null default now(),
  contexto      jsonb,
  criado_em     timestamptz not null default now()
);
comment on table core.gatilho_evento is 'DERIVADO. Disparos do motor de gatilhos (regras determinísticas).';
create index gatilho_evento_titular_idx on core.gatilho_evento (titular_id, disparado_em);

create table core.memorando (
  id          uuid primary key default gen_random_uuid(),
  titular_id  uuid not null references core.titular(id) on delete cascade,
  tipo        text not null check (tipo in ('analise','monitoramento')),
  conteudo_md text,
  payload_llm jsonb,            -- payload ANONIMIZADO enviado à LLM (sem PII)
  modelo_llm  text,             -- provider/modelo usado (observabilidade)
  gerado_em   timestamptz not null default now(),
  criado_em   timestamptz not null default now()
);
comment on table  core.memorando            is 'DERIVADO. Narrativa gerada pela LLM sobre números já calculados.';
comment on column core.memorando.payload_llm is 'Payload ANONIMIZADO de entrada da LLM (sem CNPJ/razão social).';
