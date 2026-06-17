-- 20260617000002_ur_efeitos_registrado.sql
-- Fase 5 — ajuste do modelo conforme a referência RaioX_Fluminense (decisão da área 2026-06-17):
--   * "Valor registrado" (claim nominal) = valor_onerado (col 12.12) — o nominal gigante, NÃO o 12.15.
--   * valor_capturado = valor_constituido_efeito (col 12.15) = "valor que trava / a pagar" (o que já
--     foi vendido e está direcionado ao beneficiário).
-- Também expõe titular da UR (col 7) e o id do contrato (col 12.16) p/ agrupar gravames (Bloco D).
-- CREATE OR REPLACE preserva o grant; security_invoker mantido.

drop view if exists core.ur_efeitos;
create view core.ur_efeitos with (security_invoker = true) as
select
  f.data_referencia                                                as data_referencia,
  u.id::text                                                       as ur_id,
  u.usuario_final_doc                                              as estabelecimento_cnpj,
  left(regexp_replace(u.usuario_final_doc, '[^0-9]', '', 'g'), 8)  as raiz_cnpj,
  coalesce(ge.grupo, left(regexp_replace(u.usuario_final_doc, '[^0-9]', '', 'g'), 8))
                                                                   as grupo_economico,
  u.arranjo                                                        as arranjo,
  u.titular_ur_doc                                                 as titular,
  u.data_liquidacao                                                as data_liquidacao,
  u.valor_total_ur                                                 as valor_ur,
  case when p.indicador_ordem_efeito ~ '^[0-9]+$'
       then p.indicador_ordem_efeito::int end                      as prioridade,
  p.beneficiario_doc                                               as beneficiario_cnpj,
  case p.regra_divisao when '1' then 'fixo' when '2' then 'percentual' end as regra,
  p.tipo_informacao_pagamento                                      as tipo_pagamento,
  p.valor_onerado                                                  as valor_registrado,   -- 12.12 (claim nominal)
  p.valor_constituido_efeito                                       as valor_capturado,    -- 12.15 (já direcionado)
  p.identificador_cerc_contrato                                    as contrato_id,        -- agrupa gravames (Bloco D)
  u.registradora_doc                                               as registradora,
  u.titular_id                                                     as titular_id,
  p.id                                                             as efeito_id
from core.ap005_ur u
join core.fonte_arquivo f on f.id = u.fonte_id
left join core.ap005_pagamento p on p.ur_id = u.id
left join core.grupo_economico ge
       on ge.raiz_cnpj = left(regexp_replace(u.usuario_final_doc, '[^0-9]', '', 'g'), 8);

comment on view core.ur_efeitos is
  'Tabela-mãe do cockpit (seção 3.1). valor_registrado=valor_onerado(12.12, claim nominal); '
  'valor_capturado=valor_constituido_efeito(12.15, valor que trava/já direcionado); '
  'contrato_id=identificador_cerc_contrato (agrupa gravames p/ Bloco D).';
grant select on core.ur_efeitos to authenticated, service_role;
