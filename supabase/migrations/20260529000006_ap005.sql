-- 20260529000006_ap005.sql
-- Fase 1a (AP005) — todo o "a receber" do cliente (agenda de Unidades de Recebível).
-- 1 linha = 1 UR (core.ap005_ur); a coluna 12 = lista de efeitos/pagamentos (core.ap005_pagamento).
-- Layout oficial CERC na ficha docs/fontes/AP005.md (nada inferido).

create table core.ap005_ur (
  id                          uuid primary key default gen_random_uuid(),
  titular_id                  uuid not null references core.titular(id)       on delete cascade,
  fonte_id                    uuid not null references core.fonte_arquivo(id) on delete cascade,
  linha                       integer not null,                  -- nº da linha no arquivo (rastreio/idempotência)
  referencia_externa          text,
  registradora_doc            text,
  credenciadora_doc           text,
  usuario_final_doc           text not null,                     -- col4 → resolve titular_id
  arranjo                     text,                              -- código cru
  data_liquidacao             date,
  titular_ur_doc              text,                              -- col7
  constituicao                text check (constituicao is null or constituicao in ('1','2')),
  valor_constituido_total     numeric,
  valor_constituido_antecip   numeric,
  valor_bloqueado             numeric,
  carteira                    text,
  valor_livre                 numeric,
  valor_total_ur              numeric,
  atualizado_em               timestamptz,
  criado_em                   timestamptz not null default now(),
  unique (fonte_id, linha)
);
comment on table core.ap005_ur is 'AP005: uma Unidade de Recebível por linha (todo o a receber do cliente).';
create index ap005_ur_idx on core.ap005_ur (titular_id, fonte_id, data_liquidacao, arranjo);

create table core.ap005_pagamento (
  id                          uuid primary key default gen_random_uuid(),
  ur_id                       uuid not null references core.ap005_ur(id) on delete cascade,
  ordem                       integer not null,                  -- posição do sub-registro na coluna 12
  titular_domicilio_doc       text,
  tipo_conta                  text check (tipo_conta is null or tipo_conta in ('CC','CD','CG','CI','PG','PP')),
  compe                       text,
  ispb                        text,
  agencia                     text,
  conta                       text,
  valor_a_pagar               numeric,
  beneficiario_doc            text,
  data_liquidacao_efetiva     date,
  valor_liquidacao_efetiva    numeric,
  regra_divisao               text check (regra_divisao is null or regra_divisao in ('1','2')),
  valor_onerado               numeric,
  tipo_informacao_pagamento   text check (tipo_informacao_pagamento is null
                                          or tipo_informacao_pagamento in ('1','2','3','4','5','6','7','8')),
  indicador_ordem_efeito      text,
  valor_constituido_efeito    numeric,
  identificador_cerc_contrato text,
  criado_em                   timestamptz not null default now()
);
comment on table core.ap005_pagamento is 'AP005 coluna 12: efeitos/beneficiários por UR (domicílio, ônus, liquidação, bloqueio...).';
create index ap005_pag_idx on core.ap005_pagamento (ur_id, tipo_informacao_pagamento);

-- RLS + grants (mesmo padrão)
alter table core.ap005_ur        enable row level security;
alter table core.ap005_pagamento enable row level security;

create policy ap005_ur_sel on core.ap005_ur
  for select to authenticated using (core.tem_acesso_titular(titular_id));
-- pagamento herda o acesso via UR (join), evitando coluna titular_id redundante
create policy ap005_pag_sel on core.ap005_pagamento
  for select to authenticated using (exists (
    select 1 from core.ap005_ur u
    where u.id = ur_id and core.tem_acesso_titular(u.titular_id)
  ));

grant select on core.ap005_ur, core.ap005_pagamento to authenticated;
grant all    on core.ap005_ur, core.ap005_pagamento to service_role;
