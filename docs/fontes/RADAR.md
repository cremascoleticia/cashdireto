# Ficha de fonte: RADAR

> Preenchida na entrevista da Fase 1a (2026-05-29) a partir da amostra real `samples/RADAR.csv`.
> Sem dicionário formal da CERC; significados confirmados pela pessoa responsável.

- **Formato do arquivo:** CSV
- **Encoding / separador / cabeçalho:** UTF-8; separador `,` (vírgula); **com** cabeçalho; decimal com `.` (ponto); sem separador de milhar.
- **Amostra real anexada em /samples/RADAR.csv:** sim (34 linhas, 10 estabelecimentos)
- **Dicionário de dados anexado:** não (não existe dicionário formal; reconstruído na entrevista)
- **Granularidade (1 linha = ?):** 1 linha = `estabelecimento × credenciadora × arranjo`. Cada linha traz 5 janelas de prazo × 4 situações (20 colunas de valor).
- **Chave/identificador da linha:** (`documento_estabelecimento_comercial`, `documento_credenciadora_sub`, `arranjo`)

## Campos (origem → canônico → transformação)

| campo_origem | tipo | descrição | → canônico (`core.agenda_ur`) | transformação |
|---|---|---|---|---|
| `documento_estabelecimento_comercial` | texto(14) | CNPJ do estabelecimento. Na amostra, todos compartilham a raiz `08625344` (matriz + filiais). | `estabelecimento_cnpj` + resolve `titular_id` | **cada estabelecimento = um titular**; upsert em `core.titular` por `cnpj`; agrupamento por CNPJ base (8 díg.) fica para fase posterior |
| `documento_credenciadora_sub` | texto(14) | CNPJ da credenciadora/sub | `credenciadora_doc` | cópia |
| `razao_social_credenciadora` | texto | nome da credenciadora | `credenciadora_nome` | cópia |
| `arranjo` | texto(3) | código do arranjo (bandeira + crédito/débito), ex.: `VCC`=Visa crédito | `arranjo` | **guardado cru, sem decodificar** (decisão do produto) |
| `valor_<situacao>_<janela>` (20 colunas) | numérico R$ | valor por situação × janela | linhas `(situacao, janela, valor)` | **unpivot** (largo → tidy): cada uma das 20 colunas vira uma linha |

### Unpivot das 20 colunas de valor
- **situações** (prefixo): `livre`, `pre`, `comprometido`, `constituido`
- **janelas** (sufixo): `0_30`, `31_60`, `61_90`, `91_120`, `120_mais`
- Geram-se **todas** as 20 células por linha de origem (inclusive zeros) → 34 × 20 = 680 registros para esta amostra.

## Datas
- O arquivo **não tem coluna de data**. A `data_referencia` vem do **nome do arquivo**, no token `_YYYYMMDD_` (padrão CERC, ex.: `CERC-AP005_44198946_20260529_0000003_ret.csv` → `2026-05-29`).
- **Fallback:** se o nome não tiver um token de data válido, usa-se a **data da análise** (data de processamento).

## Valores monetários
- Unidade **R$**, 2 casas decimais, ponto decimal, sem separador de milhar. **Sempre ≥ 0** (confirmado: nenhum negativo na amostra).

## Domínios/códigos a mapear
- `arranjo`: **não será decodificado** nesta fase — guardado como código cru. (Sem `dicts/arranjo.yaml`.)

## Significado das situações (confirmado na entrevista)
- **`constituido`** = valor de venda já realizada que será **recebido naquela janela** (a agenda em si). Ex.: venda feita no passado, liquidação cai em D+0–30 → entra em `constituido_0_30`.
- **`comprometido`** = parcela do constituído que foi **dada como garantia/cedida a terceiros** (onerado).
- **`livre`** = parcela do constituído **não onerada** (disponível).
- **`pre`** = significado **não confirmado**; **100% zerado** em toda a amostra. Guardado fielmente; a investigar se aparecer com valor.

### ⚠️ Relação entre situações — NÃO assumir `constituido = livre + comprometido`
Validação na amostra (script): `pre` é sempre 0, mas a igualdade `constituido = livre + comprometido` **falha em 7 de 170 células**, em dois padrões:
- janela `0_30`: `livre + comprometido > constituido` (ex.: estab `…000289`/MCC/`0_30`: 67.787,89 + 202.144,77 = 269.932,66 ≠ 237.784,77; nas demais janelas da mesma linha bate exato);
- janela `31_60`: `constituido` aparece com `livre = comprometido = 0` (ex.: estab `…001501`/ACC).

**Conclusão:** o parser grava as 4 situações **fielmente, sem derivar relação**. O cálculo de oneração/cobertura (e a relação correta entre as situações) é decidido na **Fase 1b/2**, não aqui.

## Papel desta fonte no produto
- **Agenda futura de recebíveis por janela de prazo** (versão menos detalhada que outras fontes). Base para estoque / oneração (livre × comprometido) / cobertura — a serem computados nas fases seguintes.

## Idempotência / reprocessamento
- `sha256` do arquivo grava `core.fonte_arquivo` (unique). Reprocessar o mesmo arquivo substitui as linhas de `agenda_ur` daquele `fonte_id` (sem duplicar).
