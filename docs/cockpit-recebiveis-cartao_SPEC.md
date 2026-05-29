# Cockpit de Recebíveis de Cartão — Build Spec (Claude Code)

> **Como usar este arquivo:** entregar ao Claude Code **uma fase por vez** (Fase 0 → valida → Fase 1 → ...).
> Cada fase tem **critério de aceite**; só avança quando passar.
> Copiar a seção **Convenções** para um `CLAUDE.md` na raiz do repositório.
>
> **Regra de ouro deste projeto: NÃO se presume nada sobre os arquivos.** Estrutura, campos,
> significado e papel de cada fonte só entram no código **depois** que o dicionário de dados
> correspondente for fornecido e registrado na ficha da fonte (seção 4). Até lá, a fonte fica
> como `PENDENTE_DICIONARIO` e nenhum parser é escrito para ela.

---

## 1. Contexto e objetivo

Produto de **capital de giro lastreado em recebíveis de cartão**. O sistema recebe **arquivos da
registradora (CERC)** — alguns na entrada (análise de crédito) e outros recorrentes (monitoramento)
— e entrega:

1. um **dashboard web** com indicadores e visualizações; e
2. um **memorando estruturado** (narrativa gerada por LLM).

**Fontes previstas (somente os nomes — sem qualquer suposição de conteúdo):**
`RADAR`, `RAIOX`, `AP005`, `AP007`, `AP013A`, `AP013B`.

> Cada uma dessas fontes só será tratada quando sua **ficha de dicionário** (seção 4) estiver
> preenchida pela pessoa responsável. O sistema é desenhado para receber as fontes de forma
> incremental, uma de cada vez.

**Premissas de produto (reversíveis, declaradas — NÃO são suposições sobre os arquivos):**
- **Multi-titular** (carteira de vários CNPJs); `titular` é a chave de tudo.
- Ingestão **em lote** (upload de arquivo), não streaming/API em tempo real.
- O **modelo canônico (seção 3) é um alvo de produto, uma hipótese** — será reconciliado contra
  cada dicionário; campos que as fontes não tiverem ficam vazios e os indicadores que dependem
  deles ficam marcados como indisponíveis. O modelo não afirma nada sobre o que os arquivos contêm.

---

## 2. Stack e princípios

- **Claude Code** = construtor. **GitHub** = repo + CI. **Supabase** = Postgres + Storage + Auth/RLS.
  **Railway** = worker de ingestão + host do Next.js. **Camada LLM** = provider-agnóstica (seção 7).
- **Princípios invioláveis:**
  1. **A LLM nunca calcula indicador.** Todo número vem de SQL/Python determinístico, testado e auditável.
     A LLM só **narra/explica/sumariza** sobre números prontos.
  2. **Nada de PII no request da LLM.** Titular vira alias (`T-001`); sem CNPJ/razão social.
  3. **Idempotência por `sha256`** do arquivo; reprocessar não duplica.
  4. **Bruto separado do canônico**; sempre reprocessável a partir do bruto.
  5. **Não escrever parser sem dicionário.** Fonte sem ficha preenchida = `PENDENTE_DICIONARIO`.
  6. **Segredos só em env.** Migrations e prompts versionados.

---

## 3. Modelo de dados canônico (ALVO — hipótese de produto)

Schema `core`. Camada de **ingestão bruta** separada da **camada canônica**.
As tabelas canônicas abaixo são o **destino desejado**; as colunas são reconciliadas contra os
dicionários na Fase 1 e podem ser ajustadas/renomeadas/removidas conforme a realidade das fontes.

```
-- Identidade
titular(id, cnpj, razao_social, alias, criado_em)          -- alias p/ a LLM (ex.: "T-001")

-- Ingestão BRUTA (fonte da verdade reprocessável)
fonte_arquivo(id, titular_id, tipo, sha256, nome_original,
              data_referencia, status, payload_bruto jsonb, erro, criado_em)
              -- tipo ∈ {RADAR, RAIOX, AP005, AP007, AP013A, AP013B}
              -- status ∈ {recebido, parseado, validado, falha, PENDENTE_DICIONARIO}

-- CANÔNICO (alvo; colunas a confirmar via dicionário)
agenda_ur(id, titular_id, fonte_id, ...campos_a_confirmar..., data_referencia)
contrato_efeito(id, titular_id, fonte_id, ...campos_a_confirmar..., data_referencia)
faturamento_tpv(id, titular_id, fonte_id, ...campos_a_confirmar...)
posicao_consolidada(id, titular_id, fonte_id, ...campos_a_confirmar..., data_referencia)

-- DERIVADO (controlado por nós, independe do layout das fontes)
indicador_snapshot(id, titular_id, indicador, valor numeric, data_referencia, detalhe jsonb)
gatilho_evento(id, titular_id, gatilho, severidade, valor_aferido, limite, disparado_em, contexto jsonb)
memorando(id, titular_id, tipo, conteudo_md, payload_llm jsonb, modelo_llm, gerado_em)
```

`...campos_a_confirmar...` = preenchido na Fase 1, fonte por fonte, a partir do dicionário.
Habilitar **RLS** em todas as tabelas (ver Convenções).

---

## 4. Ficha de fonte (preenchida pela pessoa, uma por etapa)

Para CADA fonte, antes de qualquer parser, criar `docs/fontes/<TIPO>.md` com esta ficha.
**Sem ficha completa, a fonte permanece `PENDENTE_DICIONARIO`.**

```
# Ficha de fonte: <TIPO>

- Formato do arquivo: (CSV | fixed-width | XML | XLSX | JSON | outro)
- Encoding / separador / cabeçalho:
- Amostra real anexada em /samples/<TIPO>.<ext>: (sim/não)
- Dicionário de dados anexado em /docs/fontes/<TIPO>_dicionario.<ext>: (sim/não)
- Granularidade (1 linha = ?):
- Chave/identificador da linha:
- Campos (origem → canônico → transformação):
  | campo_origem | tipo | descrição | → campo_canônico | transformação |
  |--------------|------|-----------|------------------|---------------|
- Campos de data e seus formatos:
- Campos monetários (unidade, escala, sinal):
- Domínios/códigos a mapear (arranjo, bandeira, credenciadora, status, tipo de efeito...):
- Papel desta fonte no produto (o que ela responde): (a definir pela pessoa)
- Observações / pegadinhas conhecidas:
```

A partir da ficha, o de-para vai para `core/parsers/<TIPO>/mapping.yaml` e os dicionários de
domínio para `core/dicts/`. **Nada é inferido pelo Claude Code** — só o que está na ficha.

---

## 5. Indicadores (definições — dependentes de dados a confirmar)

Calculados por `data_referencia`, gravados em `indicador_snapshot`. **Cada indicador declara as
fontes/campos de que depende; se o dado não existir após a reconciliação, o indicador fica
`indisponível` (não é estimado).** Catálogo-alvo:

- **Estoque/oneração:** `estoque_total`, `estoque_onerado`, `pct_janela_onerada = onerado/total`,
  `onerado_proprio`, `onerado_terceiros = onerado − próprio` (erosão de cobertura).
- **Cobertura:** `cobertura = onerado_proprio / saldo_exposicao` vs. `cobertura_minima`;
  `headroom = onerado_proprio − saldo_exposicao × cobertura_minima`.
- **Agenda futura:** `agenda_por_bucket` {D+1–30, 31–60, 61–90, 90+}; `prazo_medio_ponderado`.
- **Faturamento/TPV:** `tpv_12m`, `var_mom`, `var_yoy`, `cagr_12m`, `sazonalidade`.
- **Concentração:** `hhi_credenciadora`, `hhi_bandeira`.
- **Realização (condicional):** `taxa_realizacao = liquidado / agenda_esperada`.

> O catálogo é a intenção de produto; a lista final sai da reconciliação (seção 10, Fase 1b).

---

## 6. Motor de gatilhos (insights determinísticos)

Regras em `core/triggers/rules.yaml`, parametrizáveis por titular. **Gatilho triplo** alvo:
1. **Cobertura:** `cobertura < cobertura_minima`.
2. **Erosão por terceiros:** salto de `onerado_terceiros / estoque_total` entre snapshots.
3. **Deterioração de geração:** queda sustentada de TPV e/ou da agenda futura.

Cada disparo grava `gatilho_evento`, alimenta o memorando e o semáforo do dashboard.
Gatilhos cujos dados não existirem ficam **desabilitados** explicitamente (não silenciosamente).

---

## 7. Camada LLM — provider-agnóstica com failover

**Objetivo:** nenhum provedor é ponto único de falha. Um **adaptador único** expõe uma interface
e roteia para uma **cadeia ordenada** de provedores; em `429`/`5xx`/timeout, tenta o próximo.
Trocar/reordenar provedores é **mudança de config**, não de código.

### Interface única (`llm/client.py` ou `.ts`)
```
generate(messages, *, json_mode=True, max_tokens, schema=None) -> { text|json, provider_usado, tentativas }
```
Responsabilidades do adaptador:
- normalizar entrada/saída entre provedores (system prompt, JSON mode);
- **anonimizar** o payload (sem PII — checagem obrigatória antes do envio);
- retry com backoff exponencial dentro do provedor, depois **failover** para o próximo;
- registrar `provider_usado` por chamada (observabilidade) em log/tabela.

### Cadeia padrão (config em `llm/providers.yaml`)
```yaml
order:
  - name: gemini
    model: gemini-2.5-flash          # primário: melhor qualidade no grátis, 1M contexto
    api: google-ai-studio
    rpm: 15
  - name: groq
    model: llama-3.3-70b-versatile   # failover rápido (LPU), quota separada
    api: openai-compatible
  - name: huggingface
    model: meta-llama/Llama-3.3-70B-Instruct  # via Inference Providers (OpenAI-compatible)
    api: openai-compatible
    base_url: https://router.huggingface.co/v1
    note: 100k creditos/mes no free; troca de modelo por config
  - name: mistral
    model: mistral-large-latest      # failover c/ melhor termo de dados (UE)
    api: openai-compatible
  # último recurso (pago, dado fechado) — habilitar só se necessário:
  # - name: anthropic
  #   model: claude-haiku
```

### Comparativo dos provedores grátis (referência — confirmar limites no signup)
| Provider | Modelo grátis | Limite grátis | Papel | Dado |
|---|---|---|---|---|
| Gemini AI Studio | 2.5 Flash | ~1.500 req/dia, 15 RPM, 1M ctx | **primário** | pode ir p/ treino |
| Groq | Llama 3.3 70B | ~30 RPM | failover rápido | terceiros |
| HF Inference Providers | Llama/Qwen via gateway | ~100k créditos/mês (2M no PRO $9) | failover flexível / troca de modelo | terceiros |
| Mistral La Plateforme | Mistral Large | ~1B tokens/mês | failover (UE) | UE |
| Anthropic (pago) | Haiku/Sonnet | — | escalonamento de qualidade | fechado |

### Prompts
Versionados em `llm/prompts/` (`PROMPT_ANALISE_v1`, `PROMPT_MONITORAMENTO_v1`).
Regra repetida no prompt: *"Você recebe números já calculados. Não recalcule nem invente valores;
apenas interprete."* Saída em **JSON puro** (sem markdown/preâmbulo), parse seguro com fallback.

---

## 8. Dashboard (Next.js + Recharts no Railway)

- `/carteira` — lista de titulares + semáforo de gatilhos.
- `/titular/[id]` — agenda por bucket/bandeira; TPV 12m + sazonalidade; cobertura vs. mínima;
  oneração própria × terceiros (área empilhada); concentração (treemap); painel de gatilhos.
- `/titular/[id]/memorando` — render + botão gerar/atualizar.
Sem `<form>` em componentes (usar `onClick`/`onChange`). Auth via Supabase.
Cada gráfico só renderiza se o indicador-fonte estiver `disponível`.

---

## 9. Memorando estruturado

Markdown gerado pela LLM a partir do payload **anonimizado** de indicadores. Seções:
resumo executivo; geração de recebíveis; estoque e oneração (própria × terceiros);
cobertura e headroom; concentração e prazos; gatilhos + recomendação.
Persistido em `memorando`; export a PDF em fase posterior.

---

## 10. Plano de fases (entregar UMA por vez)

**Fase 0 — Fundação**
Repo + CI; Supabase com schema `core` (tabelas de identidade, bruta e derivada); RLS; Storage; envs.
*Aceite:* migrations sobem do zero; RLS bloqueia acesso cross-titular em teste. (Independe de dicionário.)

**Fase 1a — Intake de UMA fonte (por vez)**
A pessoa entrega: amostra real em `/samples/<TIPO>` + dicionário + **ficha preenchida** (seção 4).
Claude Code escreve o parser **apenas** dessa fonte (bruto → canônico) + mapping.yaml + testes contra a amostra.
*Aceite:* amostra parseada bate com snapshot esperado; validações de nulos/datas/somatórios passam.
Repetir 1a para cada fonte, na ordem que a pessoa definir.

**Fase 1b — Reconciliação dicionário ↔ modelo canônico**
Após as fontes necessárias estarem em 1a, consolidar quais campos canônicos existem de fato e
**marcar indicadores/gatilhos como disponíveis ou indisponíveis**.
*Aceite:* documento `docs/reconciliacao.md` lista cada indicador e a fonte/campo que o sustenta (ou o marca indisponível).

**Fase 2 — Indicadores**
Implementar só os indicadores marcados `disponível` em 1b; gravar em `indicador_snapshot`.
*Aceite:* testes de fórmula passam sobre as amostras reais.

**Fase 3 — Motor de gatilhos**
`rules.yaml` + avaliação + `gatilho_evento`; gatilhos sem dado ficam desabilitados explicitamente.
*Aceite:* casos de teste disparam/não disparam cada perna corretamente.

**Fase 4 — Dashboard**
Rotas da seção 8 com dados reais; gráficos condicionados à disponibilidade do indicador.
*Aceite:* carteira e visão de titular renderizam a partir das amostras.

**Fase 5 — Camada LLM + memorando**
Adaptador provider-agnóstico (seção 7) com cadeia de failover, anonimização e JSON; prompts; memorando.
*Aceite:* memorando gerado de payload anonimizado (sem PII no request); failover testado (simular 429 no primário → cai pro próximo); `provider_usado` logado.

---

## 11. Convenções (copiar para `CLAUDE.md`)

- **A LLM nunca calcula indicador.** Número = SQL/Python testado.
- **Nada de PII no request da LLM** (titular = alias; sem CNPJ/razão social). Checagem antes do envio.
- **Não escrever parser sem ficha de dicionário preenchida.** Não inferir layout/papel de arquivo.
- **Idempotência por `sha256`**; reprocessar não duplica.
- **Bruto separado do canônico**; sempre reprocessável.
- **LLM atrás de adaptador único** com cadeia de failover configurável; trocar provedor = mudar config.
- **RLS em todas as tabelas**; sem `SECURITY DEFINER` sem revisão; Storage privado.
- **Segredos só em env.** Migrations e prompts versionados (`_vN`).
- **Indicador/gatilho sem dado = marcado indisponível/desabilitado**, nunca estimado em silêncio.
- Commits pequenos por fase; PR por fase com o critério de aceite no corpo.
