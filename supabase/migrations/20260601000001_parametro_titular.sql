-- 20260601000001_parametro_titular.sql
-- Fase 2 — parâmetros de produto por titular (NÃO vêm da CERC). Hoje guarda o detentor_proprio,
-- usado para separar oneração própria × de terceiros. Anulável: enquanto vazio, os indicadores
-- onerado_proprio/onerado_terceiros ficam disponíveis-porém-vazios (nunca estimados — regra 9).

create table core.parametro_titular (
  titular_id        uuid primary key references core.titular(id) on delete cascade,
  detentor_proprio  text[],            -- CNPJ(s) da cashdireto como detentor/beneficiário; NULL = não definido
  cobertura_minima  numeric,           -- alvo opcional nosso (a cobertura "oficial" vem do AP013C)
  atualizado_em     timestamptz not null default now(),
  criado_em         timestamptz not null default now()
);
comment on table  core.parametro_titular            is 'Fase 2: parâmetros de produto por titular (fora da CERC).';
comment on column core.parametro_titular.detentor_proprio is 'CNPJ(s) próprios; NULL = oneração própria×terceiros fica indisponível (não estimar).';

alter table core.parametro_titular enable row level security;

create policy parametro_titular_sel on core.parametro_titular
  for select to authenticated using (core.tem_acesso_titular(titular_id));

grant select on core.parametro_titular to authenticated;
grant all    on core.parametro_titular to service_role;
