import pytest

from cashdireto_worker.config import Settings


def test_from_env_ok():
    env = {
        "SUPABASE_URL": "https://proj.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "service-key",
        "DATABASE_URL": "postgres://u:p@h:5432/db",
    }
    s = Settings.from_env(env)
    assert s.supabase_url == "https://proj.supabase.co"
    assert s.database_url.startswith("postgres://")
    assert s.storage_bucket == "fontes"            # default
    assert s.llm_providers_path == "llm/providers.yaml"


def test_from_env_overrides_optional():
    env = {
        "SUPABASE_URL": "u",
        "SUPABASE_SERVICE_ROLE_KEY": "k",
        "DATABASE_URL": "d",
        "STORAGE_BUCKET": "outro",
    }
    assert Settings.from_env(env).storage_bucket == "outro"


def test_from_env_missing_raises():
    with pytest.raises(RuntimeError) as exc:
        Settings.from_env({"SUPABASE_URL": "u"})
    assert "DATABASE_URL" in str(exc.value)
