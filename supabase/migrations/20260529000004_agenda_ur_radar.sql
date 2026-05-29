-- 20260529000004_agenda_ur_radar.sql
-- Fase 1a (RADAR) — colunas de conteúdo da agenda_ur no modelo TIDY (1 linha por situação×janela)
-- + gerador de alias sequencial do titular. Nada inferido: layout vem da ficha docs/fontes/RADAR.md.

-- Alias anônimo do titular (T-0001, T-0002, ...). `id` (uuid) segue sendo a PK; o alias é o
-- rótulo SEM PII usado nos payloads da LLM.
create sequence if not exists core.titular_alias_seq;
alter table core.titular
  alter column alias set default 'T-' || lpad(nextval('core.titular_alias_seq')::text, 4, '0');

-- Titular é identificado por CNPJ → permite upsert idempotente na ingestão.
alter table core.titular add constraint titular_cnpj_uniq unique (cnpj);

-- Reconciliação: um arquivo RADAR abrange VÁRIOS estabelecimentos (titulares). fonte_arquivo
-- deixa de exigir um titular único; a ligação por titular passa a ser por linha em agenda_ur.
alter table core.fonte_arquivo alter column titular_id drop not null;

-- Conteúdo do RADAR (tabela está vazia; colunas entram NOT NULL onde a fonte sempre traz dado).
alter table core.agenda_ur
  add column estabelecimento_cnpj text    not null,
  add column credenciadora_doc    text    not null,
  add column credenciadora_nome   text,
  add column arranjo              text    not null,
  add column janela               text    not null,
  add column situacao             text    not null,
  add column valor                numeric not null;

alter table core.agenda_ur
  add constraint agenda_ur_janela_chk
    check (janela   in ('0_30','31_60','61_90','91_120','120_mais')),
  add constraint agenda_ur_situacao_chk
    check (situacao in ('livre','pre','comprometido','constituido')),
  add constraint agenda_ur_valor_nonneg_chk
    check (valor >= 0);

comment on column core.agenda_ur.estabelecimento_cnpj is 'CNPJ do estabelecimento (origem RADAR); cada estabelecimento = um titular.';
comment on column core.agenda_ur.arranjo  is 'Código do arranjo (bandeira+crédito/débito), guardado cru, sem decodificar.';
comment on column core.agenda_ur.situacao is 'livre|pre|comprometido|constituido — gravado fielmente; relação NÃO derivada aqui.';
comment on column core.agenda_ur.janela   is 'Janela de prazo em dias a partir de data_referencia: 0_30|31_60|61_90|91_120|120_mais.';

create index agenda_ur_radar_idx
  on core.agenda_ur (titular_id, data_referencia, arranjo, janela, situacao);
