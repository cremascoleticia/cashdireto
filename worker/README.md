# Worker de ingestão

Python 3.11+. Na **Fase 0** contém apenas o scaffold de configuração (`cashdireto_worker.config`).
A ingestão de fontes (bruto → canônico) entra na **Fase 1**, uma fonte por vez, e somente após a
ficha de dicionário correspondente em `docs/fontes/<TIPO>.md`.

## Dev

```bash
pip install -e ".[dev]"
pytest -q
```

Config é lida só de variáveis de ambiente (ver `../.env.example`):

```python
from cashdireto_worker.config import Settings
settings = Settings.from_env()   # exige SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, DATABASE_URL
```

> A `service_role` key (BYPASSRLS) vive **só** no worker — nunca no front.
