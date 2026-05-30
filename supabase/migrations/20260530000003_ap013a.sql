-- 20260530000003_ap013a.sql
-- Fase 1a (AP013A) — resumo AGREGADO por Detentor (financiador): totais consolidados da carteira.
-- 1 linha = 1 detentor (core.ap013a_resumo). NÃO tem contratante/titular → tabela própria, sem FK
-- a core.titular e fora da RLS multi-titular. Dicionário oficial CERC na ficha docs/fontes/AP013A.md.
-- Decisão de produto: só equipe interna vê → leitura liberada a todo usuário autenticado.

create table core.ap013a_resumo (
  id                                      uuid primary key default gen_random_uuid(),
  fonte_id                                uuid not null references core.fonte_arquivo(id) on delete cascade,
  linha                                   integer not null,        -- nº da linha no arquivo (rastreio/idempotência)
  detentor_doc                            text not null,           -- col1 (CNPJ completo) — chave/dimensão
  qtd_contratos                           integer,
  qtd_contratantes                        integer,
  valor_saldo_devedor_total               numeric,
  qtd_ur_constituidas                     integer,
  qtd_ur_nao_constituidas                 integer,
  qtd_efeitos                             integer,
  valor_efeitos_solicitados               numeric,
  valor_efeitos_calculados_cerc           numeric,                 -- o que o financiador deve esperar onerar
  valor_efeitos_calculados_credenciadoras numeric,                 -- o que de fato será onerado (esperado ~ cerc)
  criado_em                               timestamptz not null default now(),
  unique (fonte_id, linha)
);
comment on table core.ap013a_resumo is 'AP013A: resumo agregado por Detentor (financiador). Sem titular — visão macro da carteira.';
comment on column core.ap013a_resumo.valor_efeitos_calculados_credenciadoras is 'Esperado ~ valor_efeitos_calculados_cerc; razão col10/col9 = aderência da oneração (Fase 2).';
create index ap013a_resumo_idx on core.ap013a_resumo (detentor_doc, fonte_id);

-- RLS: sem titular para ancorar. Produto é interno (só a equipe vê) → leitura liberada a authenticated.
alter table core.ap013a_resumo enable row level security;

create policy ap013a_resumo_sel on core.ap013a_resumo
  for select to authenticated using (true);

grant select on core.ap013a_resumo to authenticated;
grant all    on core.ap013a_resumo to service_role;
