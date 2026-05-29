-- 20260529000005_raiox.sql
-- Fase 1a (RAIOX) — dossiê do cliente (CERC/KYP "Raio-X do Cliente").
-- Cadastro enriquece core.titular; 3 tabelas dedicadas (tidy) para cards, série mensal e
-- relacionamentos. Os números dos cards são FATO DA FONTE (origem CERC) — separados do
-- nosso core.indicador_snapshot. Layout vem da ficha docs/fontes/RAIOX.md (nada inferido).

-- Cadastro do cliente (vem do Raio-X)
alter table core.titular
  add column natureza_juridica  text,
  add column setor_economico    text,
  add column situacao_cadastral text;

-- ── Cards / indicadores (origem CERC) ──
create table core.raiox_indicador (
  id              uuid primary key default gen_random_uuid(),
  titular_id      uuid not null references core.titular(id)       on delete cascade,
  fonte_id        uuid not null references core.fonte_arquivo(id) on delete cascade,
  data_referencia date,
  chave           text not null,
  valor           numeric,
  unidade         text check (unidade in ('reais','percentual','indice','contagem')),
  texto_extra     text,
  definicao       text,
  criado_em       timestamptz not null default now()
);
comment on table core.raiox_indicador is 'Cards do Raio-X (origem CERC, já calculados pela fonte). NÃO confundir com indicador_snapshot (nossos cálculos).';
create index raiox_indicador_idx on core.raiox_indicador (titular_id, fonte_id, chave);

-- ── Série mensal (agenda / volume_antecipacao) — reconstruída e RECONCILIADA com os cards ──
create table core.raiox_serie_mensal (
  id          uuid primary key default gen_random_uuid(),
  titular_id  uuid not null references core.titular(id)       on delete cascade,
  fonte_id    uuid not null references core.fonte_arquivo(id) on delete cascade,
  competencia date not null,                       -- 1º dia do mês de competência
  serie       text not null check (serie in ('agenda','volume_antecipacao')),
  valor       numeric not null check (valor >= 0),
  criado_em   timestamptz not null default now()
);
comment on table core.raiox_serie_mensal is 'Série mensal reconstruída da geometria do gráfico; gravada só após reconciliar com os cards.';
create index raiox_serie_idx on core.raiox_serie_mensal (titular_id, fonte_id, competencia, serie);

-- ── Quadro de relacionamentos ──
create table core.raiox_relacionamento (
  id          uuid primary key default gen_random_uuid(),
  titular_id  uuid not null references core.titular(id)       on delete cascade,
  fonte_id    uuid not null references core.fonte_arquivo(id) on delete cascade,
  tipo        text not null check (tipo in ('socio_comum','instituicao_pagamento','financiador')),
  nome        text not null,
  percentual  numeric,                              -- nulo p/ sócios (sem %)
  criado_em   timestamptz not null default now()
);
create index raiox_rel_idx on core.raiox_relacionamento (titular_id, fonte_id, tipo);

-- ── RLS + grants (mesmo padrão das demais tabelas core) ──
alter table core.raiox_indicador      enable row level security;
alter table core.raiox_serie_mensal   enable row level security;
alter table core.raiox_relacionamento enable row level security;

create policy raiox_indicador_sel on core.raiox_indicador
  for select to authenticated using (core.tem_acesso_titular(titular_id));
create policy raiox_serie_sel on core.raiox_serie_mensal
  for select to authenticated using (core.tem_acesso_titular(titular_id));
create policy raiox_rel_sel on core.raiox_relacionamento
  for select to authenticated using (core.tem_acesso_titular(titular_id));

grant select on core.raiox_indicador, core.raiox_serie_mensal, core.raiox_relacionamento to authenticated;
grant all    on core.raiox_indicador, core.raiox_serie_mensal, core.raiox_relacionamento to service_role;
