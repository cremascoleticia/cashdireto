-- 20260617000001_ur_efeitos_e_operacao.sql
-- Fase 5 (cockpit de monitoramento) — camada de INPUT da seção 3 do spec do portal.
-- A tabela-mãe `ur_efeitos` (grão = UR × efeito) é materializada como VIEW sobre o AP005 já
-- carregado (decisão: valor_ur ← ap005_ur.valor_total_ur; valor_constituido ← valor_constituido_efeito
-- = col 12.15, o realizado, NÃO o valor_onerado 12.12). As demais tabelas (operação, faturamento,
-- repasse, ingestão) são dados operacionais FORA da CERC — criadas vazias, preenchidas quando chegarem.

-- ───────── grupo econômico (mapa raiz de CNPJ → grupo; sem linha, o grupo é a própria raiz) ─────────
create table core.grupo_economico (
  raiz_cnpj  text primary key,               -- raiz de CNPJ (8 dígitos, só números)
  grupo      text not null,                  -- nome/id do grupo (pode abranger várias raízes)
  criado_em  timestamptz not null default now()
);
comment on table core.grupo_economico is
  'Mapa raiz de CNPJ → grupo econômico (fora da CERC). Sem linha, o grupo é a própria raiz (não estima).';
alter table core.grupo_economico enable row level security;
create policy grupo_economico_sel on core.grupo_economico for select to authenticated using (true);
grant select on core.grupo_economico to authenticated;
grant all    on core.grupo_economico to service_role;

-- ───────── ur_efeitos — tabela-mãe (VIEW, grão = UR × efeito), seção 3.1 ─────────
-- security_invoker: a RLS de core.ap005_ur/ap005_pagamento se aplica a QUEM CONSULTA (não bypassa).
-- LEFT JOIN no pagamento: URs sem efeito ainda aparecem (1 linha, efeito nulo) p/ a "agenda total/livre".
create view core.ur_efeitos with (security_invoker = true) as
select
  f.data_referencia                                                as data_referencia,
  u.id::text                                                       as ur_id,
  u.usuario_final_doc                                              as estabelecimento_cnpj,
  left(regexp_replace(u.usuario_final_doc, '[^0-9]', '', 'g'), 8)  as raiz_cnpj,
  coalesce(ge.grupo, left(regexp_replace(u.usuario_final_doc, '[^0-9]', '', 'g'), 8))
                                                                   as grupo_economico,
  u.arranjo                                                        as arranjo,
  u.data_liquidacao                                                as data_liquidacao,
  u.valor_total_ur                                                 as valor_ur,
  case when p.indicador_ordem_efeito ~ '^[0-9]+$'
       then p.indicador_ordem_efeito::int end                      as prioridade,
  p.beneficiario_doc                                               as beneficiario_cnpj,
  case p.regra_divisao when '1' then 'fixo' when '2' then 'percentual' end as regra,
  p.valor_constituido_efeito                                       as valor_constituido,
  u.registradora_doc                                               as registradora,
  -- colunas de apoio (rastreio/joins internos; não fazem parte do contrato visual)
  u.titular_id                                                     as titular_id,
  p.id                                                             as efeito_id
from core.ap005_ur u
join core.fonte_arquivo f on f.id = u.fonte_id
left join core.ap005_pagamento p on p.ur_id = u.id
left join core.grupo_economico ge
       on ge.raiz_cnpj = left(regexp_replace(u.usuario_final_doc, '[^0-9]', '', 'g'), 8);
comment on view core.ur_efeitos is
  'Tabela-mãe do cockpit (seção 3.1): 1 linha por UR×efeito, derivada do AP005. '
  'valor_ur=ap005_ur.valor_total_ur; valor_constituido=ap005_pagamento.valor_constituido_efeito (12.15).';
grant select on core.ur_efeitos to authenticated, service_role;

-- ───────── operação de crédito (3.2) ─────────
create table core.operacao (
  id                        uuid primary key default gen_random_uuid(),
  cedente_grupo             text not null,                 -- grupo econômico do cedente
  saldo_devedor             numeric not null,
  rg_minimo                 numeric not null,              -- gatilho da Razão de Garantia (RG)
  baseline_faturamento_dia  numeric,
  taxa_am                   numeric,                       -- taxa % a.m.
  prazo_meses               integer,
  carencia_meses            integer,
  data_desembolso           date,
  criado_em                 timestamptz not null default now()
);
comment on table core.operacao is 'Operação de crédito (capital de giro). Dado operacional, fora da CERC.';

create table core.parcela (
  id              uuid primary key default gen_random_uuid(),
  operacao_id     uuid not null references core.operacao(id) on delete cascade,
  competencia_mes date not null,                           -- 1º dia do mês de competência
  valor_parcela   numeric not null,
  criado_em       timestamptz not null default now(),
  unique (operacao_id, competencia_mes)
);

-- ───────── faturamento diário (3.3) ─────────
create table core.faturamento_diario (
  id                   uuid primary key default gen_random_uuid(),
  data                 date not null,
  estabelecimento_cnpj text not null,
  credenciadora        text,
  arranjo              text,
  valor_bruto          numeric,
  valor_liquido        numeric,
  diluicao             numeric,                            -- chargeback + cancelamento + ajuste
  criado_em            timestamptz not null default now()
);
create index faturamento_diario_idx on core.faturamento_diario (data, estabelecimento_cnpj);

-- ───────── repasse diário (3.4) — conciliação AP013 × extrato do domicílio ─────────
create table core.repasse_diario (
  id              uuid primary key default gen_random_uuid(),
  data            date not null,
  operacao_id     uuid not null references core.operacao(id) on delete cascade,
  valor_esperado  numeric,
  valor_realizado numeric,
  criado_em       timestamptz not null default now(),
  unique (operacao_id, data)
);

-- ───────── ingestão de arquivos (3.5) — evidência ausente = evidência negativa (seção 8) ─────────
create table core.ingestao_arquivos (
  id                  uuid primary key default gen_random_uuid(),
  data                date not null,
  tipo                text not null check (tipo in ('AP005','AP013','ajustes','extrato_domicilio','raiox')),
  status              text not null check (status in ('ok','ausente','erro_schema','quarentena')),
  horario_recebimento timestamptz,
  hash                text,
  criado_em           timestamptz not null default now()
);
create index ingestao_arquivos_idx on core.ingestao_arquivos (data, tipo);

-- RLS: produto interno (equipe) — leitura para authenticated, escrita só service_role (mesmo padrão AP013A).
alter table core.operacao           enable row level security;
alter table core.parcela            enable row level security;
alter table core.faturamento_diario enable row level security;
alter table core.repasse_diario     enable row level security;
alter table core.ingestao_arquivos  enable row level security;

create policy operacao_sel           on core.operacao           for select to authenticated using (true);
create policy parcela_sel            on core.parcela            for select to authenticated using (true);
create policy faturamento_diario_sel on core.faturamento_diario for select to authenticated using (true);
create policy repasse_diario_sel     on core.repasse_diario     for select to authenticated using (true);
create policy ingestao_arquivos_sel  on core.ingestao_arquivos  for select to authenticated using (true);

grant select on core.operacao, core.parcela, core.faturamento_diario, core.repasse_diario,
                core.ingestao_arquivos to authenticated;
grant all    on core.operacao, core.parcela, core.faturamento_diario, core.repasse_diario,
                core.ingestao_arquivos to service_role;
