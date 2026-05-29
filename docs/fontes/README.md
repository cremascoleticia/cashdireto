# docs/fontes — fichas de dicionário das fontes

Cada fonte CERC só vira parser **depois** que sua ficha aqui estiver completa. Sem ficha completa,
a fonte fica `PENDENTE_DICIONARIO` e **nada é inferido** sobre layout, campos ou papel do arquivo.

Para iniciar a Fase 1a de uma fonte, crie `docs/fontes/<TIPO>.md` a partir do template abaixo
(seção 4 do SPEC) e anexe a amostra real em `samples/<TIPO>.<ext>`.

Status das fontes:

| Fonte  | Ficha | Amostra | Status               |
|--------|-------|---------|----------------------|
| RADAR  | ✅    | ✅      | **parseado/validado** (Fase 1a — `agenda_ur` tidy) |
| RAIOX  | ❌    | ❌      | PENDENTE_DICIONARIO  |
| AP005  | ❌    | ❌      | PENDENTE_DICIONARIO  |
| AP007  | ❌    | ❌      | PENDENTE_DICIONARIO  |
| AP013A | ❌    | ❌      | PENDENTE_DICIONARIO  |
| AP013B | ❌    | ❌      | PENDENTE_DICIONARIO  |

## Template da ficha (`docs/fontes/<TIPO>.md`)

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
- Papel desta fonte no produto (o que ela responde):
- Observações / pegadinhas conhecidas:
```
