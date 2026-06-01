-- 20260601000002_indicador_snapshot_escopo.sql
-- Fase 2 (runner): cada snapshot é etiquetado por escopo — 'loja' (1 estabelecimento/CNPJ) ou
-- 'grupo' (raiz de CNPJ = matriz + filiais). Em grupo não há titular único: titular_id fica nulo
-- e cnpj_raiz é preenchido.

alter table core.indicador_snapshot
  add column if not exists escopo    text not null default 'loja' check (escopo in ('loja','grupo')),
  add column if not exists cnpj_raiz text;
alter table core.indicador_snapshot alter column titular_id drop not null;

comment on column core.indicador_snapshot.escopo    is 'loja (1 estabelecimento) ou grupo (raiz de CNPJ).';
comment on column core.indicador_snapshot.cnpj_raiz is 'preenchido quando escopo=grupo (titular_id nulo nesse caso).';

create index if not exists indicador_snapshot_grupo_idx
  on core.indicador_snapshot (escopo, cnpj_raiz, indicador, data_referencia);

-- RLS: produto é interno (só a equipe vê). Linhas de grupo (sem titular) ficam legíveis por
-- qualquer usuário autenticado; linhas de loja seguem o acesso por titular.
drop policy if exists indicador_snapshot_sel on core.indicador_snapshot;
create policy indicador_snapshot_sel on core.indicador_snapshot
  for select to authenticated
  using (escopo = 'grupo' or core.tem_acesso_titular(titular_id));
