-- 20260530000002_ap013.sql
-- Fase 1a (AP013 legado) — verificação da situação dos contratos: valores constituídos das URs,
-- ônus e PRIORIDADE de recebimento (col 13.10). 1 linha = 1 contrato (core.ap013_contrato);
-- a coluna 13 = lista de URs alcançadas (core.ap013_ur). A coluna 14 (indicadores de consistência)
-- é guardada BRUTA (parse estruturado pendente de amostra — ver docs/fontes/AP013.md).
-- Dicionário oficial CERC na ficha; layout físico assumido = padrão AP005/AP007 (nada inferido além disso).

create table core.ap013_contrato (
  id                                uuid primary key default gen_random_uuid(),
  titular_id                        uuid not null references core.titular(id)       on delete cascade,
  fonte_id                          uuid not null references core.fonte_arquivo(id) on delete cascade,
  linha                             integer not null,            -- nº da linha no arquivo (rastreio/idempotência)
  referencia_externa                text,
  identificador_contrato            text,
  contratante_doc                   text not null,               -- col3 → resolve titular_id
  repactuacao                       text check (repactuacao is null or repactuacao in ('0','1')),
  identificador_contrato_anterior   text,                        -- col5 (singular); obrigatório se repactuacao=1
  participante_doc                  text,
  detentor_doc                      text,
  tipo_efeito                       text check (tipo_efeito is null or tipo_efeito in ('1','2','3','4','8')),
  saldo_devedor                     numeric,
  limite_operacao_garantida         numeric,
  valor_a_manter                    numeric,
  data_vencimento                   date,
  indicadores_consistencia_raw      text,                        -- col14 BRUTO (parse estruturado pendente de amostra)
  qtd_ur_alcancadas                 numeric,
  valor_ur_alcancadas               numeric,
  resultado_distribuicao_onus       text check (resultado_distribuicao_onus is null
                                                or resultado_distribuicao_onus in ('0','1','2','3')),
  criado_em                         timestamptz not null default now(),
  unique (fonte_id, linha)
);
comment on table core.ap013_contrato is 'AP013: situação do contrato (valores constituídos, ônus, prioridade) por linha.';
comment on column core.ap013_contrato.indicadores_consistencia_raw is 'Coluna 14 guardada bruta; parse estruturado pendente de amostra real.';
create index ap013_contrato_idx on core.ap013_contrato (titular_id, fonte_id, tipo_efeito, data_vencimento);

create table core.ap013_ur (
  id                          uuid primary key default gen_random_uuid(),
  contrato_id                 uuid not null references core.ap013_contrato(id) on delete cascade,
  ordem                       integer not null,                  -- posição da UR na coluna 13
  entidade_registradora_doc   text,
  credenciadora_doc           text,
  usuario_final_doc           text,
  arranjo                     text,
  data_liquidacao             date,
  titular_ur_doc              text,
  constituicao                text check (constituicao is null or constituicao in ('1','2')),
  valor_constituido_total     numeric,
  valor_bloqueado             numeric,
  indicador_oneracao          text,                              -- 0=insucesso; 1..N=prioridade do ônus (cru)
  regra_divisao               text check (regra_divisao is null or regra_divisao in ('1','2')),
  valor_onerado               numeric,
  referencia_externa          text,
  valor_constituido_efeito    numeric,
  criado_em                   timestamptz not null default now()
);
comment on table  core.ap013_ur is 'AP013 coluna 13: URs alcançadas pelo contrato (com prioridade de oneração 13.10).';
comment on column core.ap013_ur.indicador_oneracao is '0=insucesso; 1..N=prioridade do ônus no recebimento da UR.';
create index ap013_ur_idx on core.ap013_ur (contrato_id, indicador_oneracao, data_liquidacao);

-- RLS + grants (mesmo padrão das demais fontes)
alter table core.ap013_contrato enable row level security;
alter table core.ap013_ur       enable row level security;

create policy ap013_contrato_sel on core.ap013_contrato
  for select to authenticated using (core.tem_acesso_titular(titular_id));
-- UR herda o acesso via contrato (join), evitando coluna titular_id redundante
create policy ap013_ur_sel on core.ap013_ur
  for select to authenticated using (exists (
    select 1 from core.ap013_contrato c
    where c.id = contrato_id and core.tem_acesso_titular(c.titular_id)
  ));

grant select on core.ap013_contrato, core.ap013_ur to authenticated;
grant all    on core.ap013_contrato, core.ap013_ur to service_role;
