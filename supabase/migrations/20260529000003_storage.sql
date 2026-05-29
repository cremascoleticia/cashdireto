-- 20260529000003_storage.sql
-- Fase 0 — Storage privado para os arquivos brutos das fontes (CERC).
--
-- Bucket PRIVADO. No Fase 0 NÃO criamos políticas públicas: apenas a service_role
-- (worker de ingestão, BYPASSRLS) lê/escreve objetos. A política de leitura por titular
-- para o app autenticado será adicionada em fase posterior, junto com a CONVENÇÃO de path
-- (ex.: <titular_id>/<TIPO>/<sha256>) — que não inferimos agora.

insert into storage.buckets (id, name, public)
values ('fontes', 'fontes', false)
on conflict (id) do nothing;
