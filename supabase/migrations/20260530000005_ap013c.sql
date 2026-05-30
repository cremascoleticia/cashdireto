-- 20260530000005_ap013c.sql
-- Fase 1a (AP013C) — resultado da redistribuição do Gestão de Colateral: situação do contrato
-- ANTES x DEPOIS (valor em suficiência, URs constituídas/a constituir, valor constituído, agenda
-- livre) + agendas anômalas. 1 linha = 1 contrato (core.ap013c_redistribuicao); sem listas.
-- Dicionário oficial CERC na ficha docs/fontes/AP013C.md; layout assumido = padrão das demais fontes.

create table core.ap013c_redistribuicao (
  id                                uuid primary key default gen_random_uuid(),
  titular_id                        uuid not null references core.titular(id)       on delete cascade,
  fonte_id                          uuid not null references core.fonte_arquivo(id) on delete cascade,
  linha                             integer not null,            -- nº da linha no arquivo (rastreio/idempotência)
  data_redistribuicao               date,                        -- col1 (data de negócio autoritativa)
  referencia_externa                text,
  contratante_doc                   text not null,               -- col3 → resolve titular_id
  participante_doc                  text,
  carteira                          text,
  valor_minimo_a_manter             numeric,
  -- antes da redistribuição
  valor_suficiencia_antes           numeric,                     -- col6 - col10
  qtd_ur_constituidas_antes         integer,
  qtd_ur_a_constituir_antes         integer,
  valor_constituido_efeitos_antes   numeric,
  -- dados de entrada da redistribuição
  valor_livre_agenda_antes          numeric,
  qtd_ur_constituidas_solicitadas   integer,
  qtd_ur_a_constituir_solicitadas   integer,
  -- depois da redistribuição
  valor_suficiencia_depois          numeric,                     -- col6 - col17
  qtd_ur_constituidas_depois        integer,
  qtd_ur_a_constituir_depois        integer,
  valor_constituido_efeitos_depois  numeric,
  -- agendas anômalas / observações (opcionais)
  valor_agenda_anomala              numeric,
  observacoes                       text,
  criado_em                         timestamptz not null default now(),
  unique (fonte_id, linha)
);
comment on table core.ap013c_redistribuicao is 'AP013C: situação do contrato antes x depois da redistribuição do Gestão de Colateral.';
comment on column core.ap013c_redistribuicao.valor_suficiencia_depois is 'col6-col17: negativo=déficit, positivo=excesso de garantia após redistribuição (cobertura/headroom).';
create index ap013c_redistribuicao_idx on core.ap013c_redistribuicao (titular_id, fonte_id, data_redistribuicao);

-- RLS + grants (mesmo padrão das fontes com titular)
alter table core.ap013c_redistribuicao enable row level security;

create policy ap013c_redistribuicao_sel on core.ap013c_redistribuicao
  for select to authenticated using (core.tem_acesso_titular(titular_id));

grant select on core.ap013c_redistribuicao to authenticated;
grant all    on core.ap013c_redistribuicao to service_role;
