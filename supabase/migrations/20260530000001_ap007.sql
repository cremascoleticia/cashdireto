-- 20260530000001_ap007.sql
-- Fase 1a (AP007) — contratos/efeitos sobre as unidades de recebíveis (oneração/garantia).
-- 1 linha = 1 contrato (core.ap007_contrato); a coluna 17 = lista de parcelas (core.ap007_parcela).
-- Dicionário oficial CERC na ficha docs/fontes/AP007.md (campos do dicionário; layout físico
-- assumido = padrão AP005 — ver suposições marcadas na ficha; nada inferido além disso).

create table core.ap007_contrato (
  id                                  uuid primary key default gen_random_uuid(),
  titular_id                          uuid not null references core.titular(id)       on delete cascade,
  fonte_id                            uuid not null references core.fonte_arquivo(id) on delete cascade,
  linha                               integer not null,            -- nº da linha no arquivo (rastreio/idempotência)
  tipo_operacao                       text check (tipo_operacao is null or tipo_operacao in ('C','A','I','B','P','R')),
  referencia_externa                  text,
  identificador_contrato              text,
  contratante_doc                     text not null,               -- col4 → resolve titular_id
  repactuacao                         text check (repactuacao is null or repactuacao in ('0','1')),
  identificadores_contrato_anterior   text[],                      -- col6 (lista); obrigatório se repactuacao=1
  participante_doc                    text,
  detentor_doc                        text,
  tipo_efeito                         text check (tipo_efeito is null or tipo_efeito in ('1','2','3','4','8')),
  saldo_devedor                       numeric,
  limite_operacao_garantida           numeric,
  valor_a_manter                      numeric,
  data_assinatura                     date,
  data_vencimento                     date,
  tipo_servico                        text check (tipo_servico is null or tipo_servico in ('1','2','3')),
  modalidade_operacao                 text check (modalidade_operacao is null or modalidade_operacao in ('1','2','3')),
  carteira                            text,
  tipo_avaliacao                      text,                        -- enumerador (tabela do manual); cru
  taxa_juros                          numeric,                     -- % a.a.
  indexador                           text check (indexador is null or indexador in ('1','2','3','4','5','6','7','8')),
  aceite_incondicional                text check (aceite_incondicional is null or aceite_incondicional in ('1','2')),
  criado_em                           timestamptz not null default now(),
  unique (fonte_id, linha)
);
comment on table core.ap007_contrato is 'AP007: um contrato/efeito por linha (oneração/garantia sobre recebíveis).';
create index ap007_contrato_idx on core.ap007_contrato (titular_id, fonte_id, tipo_efeito, data_vencimento);

create table core.ap007_parcela (
  id              uuid primary key default gen_random_uuid(),
  contrato_id     uuid not null references core.ap007_contrato(id) on delete cascade,
  ordem           integer not null,            -- posição da parcela na coluna 17
  data_parcela    date,
  valor_parcela   numeric,
  criado_em       timestamptz not null default now()
);
comment on table core.ap007_parcela is 'AP007 coluna 17: parcelas do contrato (obrigatório se modalidade=2 Parcelado).';
create index ap007_parcela_idx on core.ap007_parcela (contrato_id, data_parcela);

-- RLS + grants (mesmo padrão das demais fontes)
alter table core.ap007_contrato enable row level security;
alter table core.ap007_parcela  enable row level security;

create policy ap007_contrato_sel on core.ap007_contrato
  for select to authenticated using (core.tem_acesso_titular(titular_id));
-- parcela herda o acesso via contrato (join), evitando coluna titular_id redundante
create policy ap007_parcela_sel on core.ap007_parcela
  for select to authenticated using (exists (
    select 1 from core.ap007_contrato c
    where c.id = contrato_id and core.tem_acesso_titular(c.titular_id)
  ));

grant select on core.ap007_contrato, core.ap007_parcela to authenticated;
grant all    on core.ap007_contrato, core.ap007_parcela to service_role;
