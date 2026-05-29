-- rls_cross_titular.sql
-- CRITÉRIO DE ACEITE DA FASE 0: o RLS bloqueia acesso cross-titular.
--
-- O teste roda numa transação e dá ROLLBACK ao final — não deixa resíduo. Requer um Postgres
-- Supabase (roles `authenticated`/`anon`, schema `auth`, função `auth.uid()` e a leitura de
-- `request.jwt.claims`). Rode contra um projeto remoto linkado ou o stack local (Docker):
--
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f supabase/tests/rls_cross_titular.sql
--   ou:  python scripts/run_rls_test.py   (lê DATABASE_URL do ambiente)
--
-- Sucesso = roda até "RLS cross-titular: OK" sem nenhuma exceção.

begin;

-- ── Seed (executado pelo role da conexão, dono/superuser → BYPASSRLS) ──
-- Dois usuários e dois titulares; cada usuário vinculado a um titular.
insert into auth.users (id, instance_id, aud, role, email)
values
  ('11111111-1111-1111-1111-111111111111',
   '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'user-a@test.local'),
  ('22222222-2222-2222-2222-222222222222',
   '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'user-b@test.local');

insert into core.titular (id, alias) values
  ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'T-AAA'),
  ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'T-BBB');

insert into core.titular_membro (titular_id, user_id) values
  ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', '11111111-1111-1111-1111-111111111111'),
  ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', '22222222-2222-2222-2222-222222222222');

insert into core.fonte_arquivo (titular_id, tipo, sha256) values
  ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'RADAR', 'sha-of-file-A'),
  ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'RADAR', 'sha-of-file-B');

-- ── Passa a atuar como o usuário A, role authenticated ──
set local role authenticated;
set local request.jwt.claims = '{"sub":"11111111-1111-1111-1111-111111111111","role":"authenticated"}';

-- ── Asserções de isolamento ──
do $$
declare n int;
begin
  -- auth.uid() deve resolver para o usuário A
  if auth.uid() <> '11111111-1111-1111-1111-111111111111' then
    raise exception 'FAIL: auth.uid() inesperado: %', auth.uid();
  end if;

  -- A enxerga só o próprio titular
  select count(*) into n from core.titular;
  if n <> 1 then raise exception 'FAIL: titular visiveis=% (esperado 1)', n; end if;

  -- ...e NUNCA o titular B
  select count(*) into n from core.titular where alias = 'T-BBB';
  if n <> 0 then raise exception 'FAIL: titular B (T-BBB) visivel para usuario A'; end if;

  -- A enxerga só o arquivo do próprio titular
  select count(*) into n from core.fonte_arquivo;
  if n <> 1 then raise exception 'FAIL: fonte_arquivo visiveis=% (esperado 1)', n; end if;

  select count(*) into n from core.fonte_arquivo where sha256 = 'sha-of-file-B';
  if n <> 0 then raise exception 'FAIL: fonte_arquivo do titular B visivel para usuario A'; end if;

  -- Vínculos: A só vê o próprio
  select count(*) into n from core.titular_membro;
  if n <> 1 then raise exception 'FAIL: titular_membro visiveis=% (esperado 1)', n; end if;

  raise notice 'RLS cross-titular: OK (usuario A enxerga apenas T-AAA)';
end $$;

reset role;
rollback;
