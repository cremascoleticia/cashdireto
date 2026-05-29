-- ci/supabase_shim.sql
-- NÃO é migration. Emula os objetos que a plataforma Supabase já provê (roles, schema `auth`,
-- `auth.users`, `auth.uid()`, schema `storage`) para que as migrations de `supabase/migrations`
-- e o teste de RLS possam rodar contra um Postgres "puro" no CI (ou local, sem o stack completo).
-- Num projeto Supabase real esses objetos já existem e este arquivo não é aplicado.

-- Roles do Supabase
do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'anon') then
    create role anon nologin noinherit;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'authenticated') then
    create role authenticated nologin noinherit;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'service_role') then
    create role service_role nologin noinherit bypassrls;
  end if;
end $$;

create extension if not exists pgcrypto;

-- schema auth + tabela users (mínima) + auth.uid()
create schema if not exists auth;
create table if not exists auth.users (
  id          uuid primary key,
  instance_id uuid,
  aud         text,
  role        text,
  email       text
);
create or replace function auth.uid()
returns uuid
language sql
stable
as $$
  select nullif(current_setting('request.jwt.claims', true)::jsonb ->> 'sub', '')::uuid
$$;

-- schema storage + buckets (mínima, para a migration de Storage)
create schema if not exists storage;
create table if not exists storage.buckets (
  id     text primary key,
  name   text not null,
  public boolean not null default false
);
