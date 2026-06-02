# Dashboard v0 — upload, processamento e indicadores

App web (FastAPI) que reaproveita todo o worker em Python: a pessoa sobe os arquivos da CERC,
o sistema detecta a fonte, carrega no banco e calcula os indicadores; a tela mostra tudo com
filtro por **estabelecimento (loja)** ou **grupo (raiz de CNPJ)**.

## Como rodar (local)

1. **Variáveis de ambiente** (`worker/.env`, ver `.env.example`): precisa de `DATABASE_URL`
   (Postgres do Supabase), `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`.
2. **Instalar deps** (inclui as do app web):
   ```
   cd worker
   pip install -e ".[web]"
   ```
3. **Subir o servidor:**
   ```
   uvicorn cashdireto_worker.webapp:criar_app --factory --reload
   ```
4. Abrir **http://localhost:8000** → página de **Upload**. Suba os arquivos e clique em
   *Processar* (ou *Recalcular* para usar o que já está no banco). Depois, **Indicadores**.

## Fluxo interno

```
upload → ingest.detectar_tipo → parser → loader (core.*) → contexto.ler_contexto
       → runner.montar_snapshots → core.indicador_snapshot (escopo loja/grupo) → tela
```

Tudo é determinístico e testado (a LLM nunca calcula). As peças puras têm testes; banco é casca fina.

## Indicadores na tela (mapa de display da área)

Renderização por bloco: **label** (card), **tabela**, **gráfico** (Chart.js).

| Fonte | Indicador | Display |
|---|---|---|
| RADAR | totais (livre/comprometido/constituído/nível) | labels |
| RADAR | por janela de tempo (constituído + comprometido) | gráfico de barras (ID2) |
| RADAR | constituído por arranjo (+ %) | tabela |
| Raio-X | 9 indicadores do dossiê | labels |
| Raio-X | histórico (agenda × antecipação) | gráfico de barras (ID1) |
| Raio-X | sócios / IP / financiadores | tabelas |
| AP005 | constituído/livre/total por usuário final, por titular | labels / gráficos por ano-mês (ID6) e tabelas |
| AP005 | efeitos por ordem/tipo/regra/beneficiário | tabelas |
| AP013 | constituído/onerado por UF (× oneração, × mês) | labels / tabelas / gráfico (ID11) |
| AP013 | valor a manter (detentor próprio) | labels |
| AP013B | calculado credenciadoras (detentor próprio) | tabela |
| AP013C | constituído e suficiência pós-redistribuição | labels |

> **v0:** os gráficos estão funcionais (Chart.js), mas o ajuste fino de cada ID (barra horizontal,
> linha de nível, eixos) é incremental — a base já mostra os números reais por loja/grupo.
> AP007 e AP013A não têm indicadores (decisão da área).
