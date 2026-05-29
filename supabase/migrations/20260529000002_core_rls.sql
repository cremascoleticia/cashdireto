-- 20260529000002_core_rls.sql
-- Fase 0 — RLS multi-titular + grants para os roles do Supabase.
--
-- Modelo de acesso: um usuário (auth.users) enxerga uma linha SE estiver vinculado, em
-- core.titular_membro, ao titular dono daquela linha. O worker de ingestão escreve usando a
-- service_role key (BYPASSRLS), então aqui só declaramos políticas de LEITURA (SELECT) para o
-- app autenticado. Escrita pelo app virá em fase posterior, com políticas próprias.
--
-- A função helper é SECURITY INVOKER (NÃO SECURITY DEFINER — conforme regra do projeto).
-- Ela lê core.titular_membro sob o RLS do próprio usuário (política `membro_self_sel` abaixo
-- só expõe as linhas onde user_id = auth.uid()), portanto não há vazamento nem recursão.

-- ───────────────────────────── Grants base ─────────────────────────────
grant usage on schema core to authenticated, anon, service_role;

-- Leitura para o app autenticado; tudo para o worker (service_role).
grant select on all tables in schema core to authenticated;
grant all    on all tables in schema core to service_role;

-- Tabelas futuras (Fase 1+) herdam os mesmos grants automaticamente.
alter default privileges in schema core grant select on tables to authenticated;
alter default privileges in schema core grant all    on tables to service_role;

-- ──────────────────────────── Helper de acesso ────────────────────────────
create or replace function core.tem_acesso_titular(p_titular uuid)
returns boolean
language sql
stable
security invoker
set search_path = core, pg_temp
as $$
  select exists (
    select 1
    from core.titular_membro m
    where m.titular_id = p_titular
      and m.user_id    = auth.uid()
  );
$$;
comment on function core.tem_acesso_titular(uuid)
  is 'True se o usuário atual (auth.uid()) está vinculado ao titular. SECURITY INVOKER por design.';
grant execute on function core.tem_acesso_titular(uuid) to authenticated, anon, service_role;

-- ──────────────────────── Habilita RLS em TODAS as tabelas ────────────────────────
alter table core.titular             enable row level security;
alter table core.titular_membro      enable row level security;
alter table core.fonte_arquivo       enable row level security;
alter table core.agenda_ur           enable row level security;
alter table core.contrato_efeito     enable row level security;
alter table core.faturamento_tpv     enable row level security;
alter table core.posicao_consolidada enable row level security;
alter table core.indicador_snapshot  enable row level security;
alter table core.gatilho_evento      enable row level security;
alter table core.memorando           enable row level security;

-- ─────────────────────────────── Políticas SELECT ───────────────────────────────
-- Usuário enxerga apenas o titular/linhas a que está vinculado.

create policy titular_sel on core.titular
  for select to authenticated using (core.tem_acesso_titular(id));

-- Vínculos: cada usuário vê apenas os próprios (base da função helper).
create policy membro_self_sel on core.titular_membro
  for select to authenticated using (user_id = auth.uid());

create policy fonte_arquivo_sel on core.fonte_arquivo
  for select to authenticated using (core.tem_acesso_titular(titular_id));

create policy agenda_ur_sel on core.agenda_ur
  for select to authenticated using (core.tem_acesso_titular(titular_id));

create policy contrato_efeito_sel on core.contrato_efeito
  for select to authenticated using (core.tem_acesso_titular(titular_id));

create policy faturamento_tpv_sel on core.faturamento_tpv
  for select to authenticated using (core.tem_acesso_titular(titular_id));

create policy posicao_consolidada_sel on core.posicao_consolidada
  for select to authenticated using (core.tem_acesso_titular(titular_id));

create policy indicador_snapshot_sel on core.indicador_snapshot
  for select to authenticated using (core.tem_acesso_titular(titular_id));

create policy gatilho_evento_sel on core.gatilho_evento
  for select to authenticated using (core.tem_acesso_titular(titular_id));

create policy memorando_sel on core.memorando
  for select to authenticated using (core.tem_acesso_titular(titular_id));
