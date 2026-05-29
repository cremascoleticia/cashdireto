# /samples — amostras reais das fontes

Coloque aqui a **amostra real** de cada fonte ao iniciar a Fase 1a dela: `samples/<TIPO>.<ext>`
(ex.: `samples/RADAR.csv`). Fontes previstas: `RADAR`, `RAIOX`, `AP005`, `AP007`, `AP013A`, `AP013B`.

⚠️ **Conteúdo real NÃO é versionado** (ver `.gitignore`) — pode conter PII/dados sensíveis.
O arquivo entra localmente só para o Claude Code escrever e testar o parser daquela fonte.

Nenhum parser é escrito sem a **ficha de dicionário** correspondente preenchida em
`docs/fontes/<TIPO>.md`. Até lá a fonte fica `PENDENTE_DICIONARIO`.
