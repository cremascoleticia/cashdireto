# Ficha de fonte: RAIOX

> Preenchida na entrevista da Fase 1a (2026-05-29). Amostra: `samples/RAIOX.html` (página do
> produto "Raio-X do Cliente" da CERC/KYP, salva do navegador). Sem dicionário formal.

- **Formato do arquivo:** HTML (página de SPA salva do navegador — React/Recharts). **Não é tabular.**
- **Encoding:** UTF-8.
- **Amostra real anexada em /samples/RAIOX.html:** sim (+ pasta `RAIOX_files/` com assets; ignorar).
- **Dicionário de dados:** não (reconstruído na entrevista; definições dos indicadores vêm dos `aria-label`).
- **Granularidade (1 arquivo = ?):** **1 cliente (titular)**. Dossiê agregado de um único CNPJ.
- **Chave/identificador:** CNPJ do cliente (no bloco de cadastro).

## ⚠️ Natureza da fonte e fragilidade
- É uma página de **SPA** com classes CSS **hasheadas** (`...customer-x-ray-XXXX`) que **mudam a cada
  exportação**. O parser **NÃO** se prende a classes — ancora nos **textos de rótulo** (estáveis,
  ex.: "Faturamento Estimado") e nos atributos `aria-label`.
- Os números **já vêm calculados pela CERC** → são gravados como **fato da fonte (origem CERC)**,
  em tabelas próprias, **separados** dos indicadores que nós calculamos (`indicador_snapshot`).

## Blocos a extrair (decisão: extrair tudo)

### 1. Cadastro → enriquece `core.titular`
| campo na tela | → canônico |
|---|---|
| Razão social | `titular.razao_social` |
| CNPJ | `titular.cnpj` (upsert; cada CNPJ = 1 titular) |
| Natureza Jurídica | `titular.natureza_juridica` |
| Setor Econômico | `titular.setor_economico` |
| Situação Cadastral | `titular.situacao_cadastral` |

### 2. Cards de indicadores (origem CERC) → `core.raiox_indicador` (tidy)
Valor **exato** vem do `aria-label` (a tela mostra abreviado: R$10M etc.). Definição também do `aria-label`.

| chave | unidade | definição (do aria-label) |
|---|---|---|
| `nivel_comprometimento` | percentual | relação entre agenda contratada futura e agendas a receber |
| `faturamento_estimado` | reais | estimativa de faturamento baseada no histórico real |
| `potencial_chargeback` | percentual | probabilidade de chargeback (ocorrências / quantidade) |
| `faturamento_medio_diario` | reais | (+ texto "% acima/abaixo do setor") |
| `agenda_mensal_media` | reais | média mensal das agendas liquidadas |
| `historico_agenda` | reais | soma dos últimos 12 meses de agendas liquidadas |
| `volume_antecipacao` | reais | soma dos últimos 12 meses de antecipação realizada |
| `indice_conformidade_risco` | indice | (0–100) |
| `fraudes_detectadas` | contagem | |
| `constatacoes_criticas` | contagem | "outros ativos" |

### 3. Série mensal → `core.raiox_serie_mensal` (tidy)
Reconstruída da **geometria das barras do SVG (Recharts)** usando a escala exata do eixo Y
(ticks rotulados `R$0 … R$600k` com posição de pixel conhecida). Coordenadas em float → erro nulo.
- séries: `agenda`, `volume_antecipacao` (a linha de **% nível de comprometimento NÃO é extraída** —
  eixo secundário sem ticks rotulados; decisão do produto).
- competência: mês a mês (ex.: mai/2025 → abr/2026), mapeado pelos rótulos do eixo X.
- **TRAVA DE RECONCILIAÇÃO (validação):** Σ(agenda mensal) deve bater com o card `historico_agenda`
  e Σ(volume mensal) com `volume_antecipacao`; média(agenda) com `agenda_mensal_media`.
  Se não reconciliar (tolerância de centavos), o parser **falha** (não grava série não-auditável).
  *(Validado na amostra: bate ao centavo — 3.785.988,79 e 4.757.612,40.)*

### 4. Quadro de relacionamentos → `core.raiox_relacionamento` (tidy)
| tipo | conteúdo |
|---|---|
| `socio_comum` | nome da empresa (sem %) |
| `instituicao_pagamento` | nome + percentual |
| `financiador` | nome + percentual |

## Datas
- O HTML **não traz data de referência** do dossiê (as datas visíveis são de notificações de outro
  produto). `data_referencia` = **data da análise** (fallback), ajustável no momento da ingestão.

## Valores monetários
- R$, 2 casas. **Exatos** via `aria-label` (não usar o texto abreviado da tela). Percentuais como fração/ра %.

## Idempotência / reprocessamento
- `sha256` do HTML em `core.fonte_arquivo` (tipo RAIOX, titular_id preenchido — fonte single-titular).
  Reprocessar substitui as linhas RAIOX daquele `fonte_id`.

## Papel desta fonte no produto
- **Dossiê do cliente (KYP):** cadastro + indicadores CERC + histórico mensal de agenda/antecipação +
  rede de relacionamentos (sócios, instituições de pagamento, financiadores). Complementa o RADAR
  (que é a agenda por janela de prazo).
