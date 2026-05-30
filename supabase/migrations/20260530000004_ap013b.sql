-- 20260530000004_ap013b.sql
-- Fase 1a (AP013B) — situação do contrato com quebra POR CREDENCIADORA alcançada.
-- 1 linha = 1 contrato (core.ap013b_contrato); a coluna 16 = lista por credenciadora
-- (core.ap013b_credenciadora). Inclui prioridade (16.9/16.10) e sobrecolateralização (col17).
-- Dicionário oficial CERC na ficha docs/fontes/AP013B.md; layout assumido = padrão AP005/AP007/AP013.

create table core.ap013b_contrato (
  id                                uuid primary key default gen_random_uuid(),
  titular_id                        uuid not null references core.titular(id)       on delete cascade,
  fonte_id                          uuid not null references core.fonte_arquivo(id) on delete cascade,
  linha                             integer not null,            -- nº da linha no arquivo (rastreio/idempotência)
  referencia_externa                text,
  identificador_contrato            text,
  contratante_doc                   text not null,               -- col3 → resolve titular_id
  repactuacao                       text check (repactuacao is null or repactuacao in ('0','1')),
  identificador_contrato_anterior   text,                        -- col5 (singular)
  participante_doc                  text,
  detentor_doc                      text,
  carteira                          text,
  tipo_servico                      text check (tipo_servico is null or tipo_servico in ('1','2','3')),
  tipo_efeito                       text check (tipo_efeito is null or tipo_efeito in ('1','2','3','4','8')),
  saldo_devedor                     numeric,
  data_criacao                      date,
  data_assinatura                   date,
  data_vencimento                   date,
  data_ultima_atualizacao           date,
  indicador_sobrecolateralizacao    numeric,                     -- col17 = efeitos(16.6)/saldo devedor(11)
  criado_em                         timestamptz not null default now(),
  unique (fonte_id, linha)
);
comment on table core.ap013b_contrato is 'AP013B: situação do contrato com quebra por credenciadora (col16) e sobrecolateralização (col17).';
create index ap013b_contrato_idx on core.ap013b_contrato (titular_id, fonte_id, tipo_efeito, data_vencimento);

create table core.ap013b_credenciadora (
  id                                      uuid primary key default gen_random_uuid(),
  contrato_id                             uuid not null references core.ap013b_contrato(id) on delete cascade,
  ordem                                   integer not null,      -- posição na coluna 16
  entidade_registradora_doc               text,
  credenciadora_doc                       text,
  qtd_ur_constituidas                     integer,
  qtd_ur_nao_constituidas                 integer,
  qtd_efeitos                             integer,
  valor_efeitos_solicitados               numeric,
  valor_efeitos_calculados_cerc           numeric,
  valor_efeitos_calculados_credenciadoras numeric,
  qtd_ur_prioridade_1                     integer,
  qtd_ur_prioridade_diferente_1           integer,
  criado_em                               timestamptz not null default now()
);
comment on table core.ap013b_credenciadora is 'AP013B coluna 16: agregados por credenciadora alcançada (com distribuição de prioridade).';
create index ap013b_credenciadora_idx on core.ap013b_credenciadora (contrato_id, credenciadora_doc);

-- RLS + grants (mesmo padrão das fontes com titular)
alter table core.ap013b_contrato      enable row level security;
alter table core.ap013b_credenciadora enable row level security;

create policy ap013b_contrato_sel on core.ap013b_contrato
  for select to authenticated using (core.tem_acesso_titular(titular_id));
-- credenciadora herda o acesso via contrato (join)
create policy ap013b_credenciadora_sel on core.ap013b_credenciadora
  for select to authenticated using (exists (
    select 1 from core.ap013b_contrato c
    where c.id = contrato_id and core.tem_acesso_titular(c.titular_id)
  ));

grant select on core.ap013b_contrato, core.ap013b_credenciadora to authenticated;
grant all    on core.ap013b_contrato, core.ap013b_credenciadora to service_role;
