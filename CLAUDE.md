# CLAUDE.md — Cockpit de Recebíveis de Cartão

Produto de capital de giro lastreado em recebíveis de cartão. O sistema lê arquivos da
registradora (CERC), calcula indicadores de crédito/monitoramento e entrega um dashboard
e um memorando narrado por LLM.

**Plano de build completo:** @docs/cockpit-recebiveis-cartao_SPEC.md
Siga-o **fase por fase**. Só avance quando o critério de aceite da fase atual passar.

**Stack:** Supabase (Postgres + Storage + Auth/RLS) · Railway (worker + Next.js) · GitHub · camada LLM provider-agnóstica.

---

## Regras invioláveis

1. **A LLM nunca calcula indicador.** Todo número vem de SQL/Python determinístico, testado e auditável. A LLM só narra/explica/sumariza sobre números prontos.
2. **Nada de PII no request da LLM.** Titular vira alias (ex.: `T-001`); sem CNPJ/razão social. Checar antes de enviar.
3. **Não escrever parser sem dicionário.** Toda fonte começa como `PENDENTE_DICIONARIO`. Só entra no código depois que a ficha em `docs/fontes/<TIPO>.md` estiver preenchida com amostra + dicionário reais. **Nunca inferir layout, campos ou papel de um arquivo.**
4. **Idempotência por `sha256`** do arquivo — reprocessar não duplica.
5. **Bruto separado do canônico** — sempre reprocessável a partir do bruto.
6. **LLM atrás de adaptador único** com cadeia de failover configurável (`llm/providers.yaml`). Trocar/reordenar provedor = mudar config, não código.
7. **RLS em todas as tabelas.** Sem `SECURITY DEFINER` sem revisão. Storage privado.
8. **Segredos só em env** (nunca commitar chave). Migrations e prompts versionados (`_vN`).
9. **Indicador/gatilho sem dado = marcado indisponível/desabilitado**, nunca estimado em silêncio.

## Fluxo de trabalho

- Comece pela **Fase 0**. Não implemente fases futuras "de bônus".
- Em caso de dúvida sobre o conteúdo de um arquivo de fonte: **pare e pergunte**, não suponha.
- Commits pequenos por fase; abra PR por fase com o critério de aceite no corpo.
- Antes de qualquer mudança de schema: usar migration versionada, nunca alterar à mão.
