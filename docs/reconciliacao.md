# Reconciliação — dicionário ↔ modelo canônico (Fase 1b)

> Consolida, após a Fase 1a (6 fontes CERC + RADAR/RAIOX), **quais campos canônicos existem de
> fato** e marca **cada indicador e gatilho** como disponível ou indisponível, citando a
> fonte/campo que o sustenta. Critério de aceite da Fase 1b (SPEC seção 10).

## Convenção de status

| Status | Significado |
|---|---|
| ✅ **disponível** | dá pra calcular de forma determinística com os campos já parseados |
| 🟡 **disponível c/ parâmetro** | calculável, mas depende de um parâmetro de produto (não vem da CERC) |
| 🟠 **disponível, pendente validação** | a lógica existe, mas a fonte foi escrita **do dicionário sem amostra real** (só AP005 tem amostra) — confirmar com arquivo de produção antes de confiar |
| 🔴 **indisponível** | falta dado/decodificação; fica explicitamente desabilitado (não estimar) |

> ⚠️ **Lastro de dados (regra 9 do CLAUDE.md):** das fontes AP, **somente o AP005 tem amostra real
> validada**. AP007/AP013/AP013A/AP013B/AP013C foram escritas a partir do dicionário, com layout
> físico assumido. Todo indicador cujo lastro principal seja uma dessas 5 fontes carrega o selo
> 🟠 até validação com amostra de produção.

---

## 1. Campos canônicos que existem de fato (por fonte)

| Fonte | Tabela(s) | Campos-chave disponíveis |
|---|---|---|
| **RADAR** | `agenda_ur` | `situacao` {livre,pre,comprometido,constituido} × `janela` {0_30,31_60,61_90,91_120,120_mais}, `valor`, `credenciadora_doc`, `arranjo`, `estabelecimento_cnpj` |
| **RAIOX** | `raiox_indicador`, `raiox_serie_mensal`, `raiox_relacionamento` | `faturamento_estimado`, `agenda_mensal_media`, série mensal {`agenda`,`volume_antecipacao`}, sócios/IPs/financiadores |
| **AP005** | `ap005_ur`, `ap005_pagamento` | `constituicao`, `valor_constituido_total`, `valor_bloqueado`, `data_liquidacao`, `valor_total_ur`, `valor_livre`; efeitos `tipo_informacao_pagamento` (1–8), `valor_onerado`, `valor_a_pagar`, `beneficiario_doc`, `data_liquidacao_efetiva`, `valor_liquidacao_efetiva`, `valor_constituido_efeito` |
| **AP007** | `ap007_contrato`, `ap007_parcela` | `tipo_efeito`, `saldo_devedor`, `limite_operacao_garantida`, `valor_a_manter`, `modalidade_operacao`, parcelas (data/valor) |
| **AP013** | `ap013_contrato`, `ap013_ur` | `saldo_devedor`, `valor_a_manter`, `qtd_ur_alcancadas`, `valor_ur_alcancadas`, `resultado_distribuicao_onus`; por UR: `indicador_oneracao` (**prioridade do ônus**), `constituicao`, `valor_onerado`, `valor_constituido_efeito` |
| **AP013A** | `ap013a_resumo` | por **detentor**: `valor_saldo_devedor_total`, `qtd_ur_constituidas`/`_nao_constituidas`, `qtd_efeitos`, `valor_efeitos_solicitados`, `valor_efeitos_calculados_cerc`, `valor_efeitos_calculados_credenciadoras` |
| **AP013B** | `ap013b_contrato`, `ap013b_credenciadora` | `indicador_sobrecolateralizacao`; por credenciadora: efeitos solicitados/CERC/credenciadora, `qtd_ur_prioridade_1`, `qtd_ur_prioridade_diferente_1` |
| **AP013C** | `ap013c_redistribuicao` | `valor_minimo_a_manter`, `valor_suficiencia_antes`/`_depois`, `valor_constituido_efeitos_antes`/`_depois`, `qtd_ur_constituidas_antes`/`_depois`, `valor_livre_agenda_antes`, `valor_agenda_anomala` |

**Lacunas estruturais observadas:**
- **Bandeira do cartão** não existe como campo: só temos `arranjo` (código cru, ex.: MCD/VCD/ECD). HHI por bandeira exige um de-para `arranjo → bandeira`.
- **"Próprio × terceiros"** (oneração nossa vs. de terceiros) exige saber **qual `detentor_doc`/`beneficiario_doc` é a cashdireto** — parâmetro de produto.
- **Exposição/cobertura mínima** do nosso contrato não vêm da CERC (são parâmetros). Mas o AP013C já traz `valor_minimo_a_manter` e `valor_suficiencia`, que dão cobertura/headroom **na ótica do contrato CERC** sem precisar do nosso parâmetro.

---

## 2. Catálogo de indicadores — SPEC seção 5

### 2.1 Estoque / oneração
| Indicador | Fórmula | Fonte.campo | Status |
|---|---|---|---|
| `estoque_total` | Σ agenda constituída | RADAR `agenda_ur.valor` (situacao=constituido) ou AP005 `valor_constituido_total` | 🟡/🟠 RADAR ✅; AP005 🟠 |
| `estoque_onerado` | Σ valor onerado | AP005 `ap005_pagamento.valor_onerado` / AP013 `ap013_ur.valor_onerado` | 🟠 |
| `pct_janela_onerada` | `estoque_onerado / estoque_total` | derivado dos dois acima | 🟠 |
| `onerado_proprio` | Σ onerado com beneficiário = nós | AP005 `beneficiario_doc` = nosso CNPJ; AP013 efeitos | 🟡 depende de parâmetro `detentor_proprio` |
| `onerado_terceiros` | `onerado − onerado_proprio` | derivado | 🟡 idem |

### 2.2 Cobertura / headroom
| Indicador | Fórmula | Fonte.campo | Status |
|---|---|---|---|
| `cobertura` | `onerado_proprio / saldo_exposicao` | AP013 `saldo_devedor` ou parâmetro de exposição | 🟡 c/ parâmetro `cobertura_minima` |
| `headroom` | `onerado_proprio − saldo_exposicao × cobertura_minima` | idem | 🟡 c/ parâmetro |
| **`suficiencia_pos_redistribuicao`** | `valor_suficiencia_depois` (déficit<0 / excesso>0) | **AP013C col.14** | 🟠 ✅ direto (não precisa do nosso parâmetro — usa `valor_minimo_a_manter` da CERC) |
| **`headroom_cerc`** | `valor_minimo_a_manter − valor_constituido_efeitos_depois` | AP013C col.6, col.17 | 🟠 |

### 2.3 Agenda futura
| Indicador | Fórmula | Fonte.campo | Status |
|---|---|---|---|
| `agenda_por_bucket` {D+1–30,31–60,61–90,90+} | Σ por janela | RADAR `agenda_ur.janela`/`valor` (✅) ou AP005 `data_liquidacao` bucketizada | RADAR ✅ / AP005 🟠 |
| `prazo_medio_ponderado` | Σ(prazo×valor)/Σvalor | AP005 `data_liquidacao` × `valor_total_ur` | 🟠 |

### 2.4 Faturamento / TPV
| Indicador | Fórmula | Fonte.campo | Status |
|---|---|---|---|
| `tpv_12m` | Σ 12 meses | RAIOX `raiox_serie_mensal` (serie=agenda) / `faturamento_estimado` | 🟡 disponível **se a série tiver ≥12 meses** (amostra tinha 2) |
| `var_mom` | mês/mês | série mensal | 🟡 idem |
| `var_yoy` | ano/ano | série mensal | 🟡 precisa ≥13 meses |
| `cagr_12m` | CAGR | série mensal | 🟡 precisa ≥12 meses |
| `sazonalidade` | índice sazonal | série mensal | 🟡 precisa ≥12 meses |

### 2.5 Concentração
| Indicador | Fórmula | Fonte.campo | Status |
|---|---|---|---|
| `hhi_credenciadora` | Σ(share²) por credenciadora | RADAR `credenciadora_doc`/`valor` ou AP013B `credenciadora_doc` | RADAR ✅ / AP013B 🟠 |
| `hhi_bandeira` | Σ(share²) por bandeira | depende de de-para `arranjo → bandeira` | 🔴 indisponível até decodificar `arranjo` |

### 2.6 Realização (condicional)
| Indicador | Fórmula | Fonte.campo | Status |
|---|---|---|---|
| `taxa_realizacao` | `liquidado / agenda_esperada` | AP005 `valor_liquidacao_efetiva` (tipo_informacao_pagamento=6) ÷ agenda RADAR/AP005 | 🟠 (precisa de ≥2 snapshots no tempo) |

---

## 3. Indicadores NOVOS destravados pela família AP013

| Indicador | Fórmula | Fonte.campo | Status |
|---|---|---|---|
| **`sobrecolateralizacao`** | quantas vezes onera além da dívida | **AP013B col.17** (`indicador_sobrecolateralizacao`, já pronto) | 🟠 ✅ direto |
| **`aderencia_oneracao`** | `calculado_credenciadoras / calculado_cerc` (esperado ≈ 1) | AP013A col.10÷col.9 (detentor) / AP013B 16.8÷16.7 (credenciadora) | 🟠 |
| **`prioridade_1_share`** | `qtd_ur_prioridade_1 / (prioridade_1 + prioridade_≠1)` | AP013B `qtd_ur_prioridade_1`/`_diferente_1` | 🟠 |
| **`distribuicao_prioridade_onus`** | histograma de `indicador_oneracao` (0=insucesso,1..N) | AP013 `ap013_ur.indicador_oneracao` | 🟠 |
| **`efeito_redistribuicao`** | `valor_suficiencia_depois − valor_suficiencia_antes` | AP013C col.14 − col.7 | 🟠 |
| **`conversao_fumaca`** | variação de URs a constituir | AP013C `qtd_ur_a_constituir_antes` → `_depois` | 🟠 |
| **`agenda_anomala`** | flag/valor de agenda anômala | AP013C `valor_agenda_anomala` | 🟠 |
| **`resultado_distribuicao_onus`** | 0=N/A,1=Suficiente,2=Insuficiente,3=Excesso | AP013 `resultado_distribuicao_onus` | 🟠 |

---

## 4. Gatilhos (Fase 3) — disponibilidade

| Gatilho | Regra | Lastro | Status |
|---|---|---|---|
| **Cobertura** | `cobertura < cobertura_minima` (ou `valor_suficiencia_depois < 0`) | AP013C col.14 (direto) ou cobertura c/ parâmetro | 🟠 ✅ via AP013C |
| **Erosão por terceiros** | salto de `onerado_terceiros / estoque_total` entre snapshots | AP005/AP013 + parâmetro `detentor_proprio` + ≥2 snapshots | 🟡 c/ parâmetro e histórico |
| **Deterioração de geração** | queda sustentada de TPV e/ou agenda futura | RAIOX série mensal + RADAR | 🟡 precisa de série temporal suficiente |

---

## 5. Parâmetros de produto necessários (não vêm da CERC)

1. **`detentor_proprio`** — CNPJ(s) da cashdireto como detentor/beneficiário, para separar oneração própria × terceiros. *(habilita onerado_proprio/terceiros e o gatilho de erosão)*
2. **`cobertura_minima` por titular** — fração mínima exigida. *(o AP013C dá uma alternativa direta via `valor_minimo_a_manter`/`suficiencia`)*
3. **De-para `arranjo → bandeira`** (tabela de arranjos do SPB). *(habilita `hhi_bandeira`)*
4. **Histórico de snapshots** (`data_referencia`) — vários indicadores de variação (var_mom/yoy, taxa_realizacao, erosão) exigem ≥2 pontos no tempo.

---

## 6. Resumo

- **Diretos / fortes:** agenda por bucket e HHI por credenciadora (RADAR ✅), cobertura/headroom e efeito da redistribuição (AP013C), sobrecolateralização (AP013B), prioridade do ônus (AP013/AP013B), aderência da oneração (AP013A/B).
- **Condicionais a parâmetro:** próprio×terceiros e cobertura clássica (precisam de `detentor_proprio`/`cobertura_minima`).
- **Condicionais a histórico:** TPV/variações, taxa de realização, gatilhos de erosão/deterioração (precisam de série temporal).
- **Indisponível hoje:** `hhi_bandeira` (falta de-para `arranjo→bandeira`).
- **Selo transversal 🟠:** tudo lastreado em AP007/AP013/AP013A/B/C precisa de validação com amostra real (só AP005 tem). **Não estimar em silêncio** o que estiver 🔴/pendente.

> **Fase 2** implementa **apenas** os ✅ e os 🟡/🟠 cujos parâmetros/validação a Letícia confirmar;
> os 🔴 ficam explicitamente desabilitados em `indicador_snapshot`/dashboard (regra 9).
