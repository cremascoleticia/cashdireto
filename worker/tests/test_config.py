import pytest

from cashdireto_worker.config import Settings, _parse_dotenv, load_dotenv_into


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


def test_parse_dotenv_handles_comments_quotes_and_special_chars():
    text = "\n".join([
        "# comentário",
        "",
        "SUPABASE_URL=https://proj.supabase.co",
        'STORAGE_BUCKET="fontes"',
        "export DATABASE_URL=postgres://u:p@ss@host:5432/db",  # senha com @ e :
        "VAZIA=",
        "SEM_IGUAL",
    ])
    parsed = _parse_dotenv(text)
    assert parsed["SUPABASE_URL"] == "https://proj.supabase.co"
    assert parsed["STORAGE_BUCKET"] == "fontes"            # aspas removidas
    assert parsed["DATABASE_URL"] == "postgres://u:p@ss@host:5432/db"
    assert parsed["VAZIA"] == ""
    assert "SEM_IGUAL" not in parsed


def test_load_dotenv_does_not_override_existing(tmp_path):
    (tmp_path / ".env").write_text(
        "SUPABASE_URL=do-arquivo\nNOVA=do-arquivo\n", encoding="utf-8"
    )
    env = {"SUPABASE_URL": "do-ambiente"}
    load_dotenv_into(env, start=tmp_path)
    assert env["SUPABASE_URL"] == "do-ambiente"   # ambiente real vence
    assert env["NOVA"] == "do-arquivo"            # arquivo preenche o que falta


def test_load_dotenv_no_file_is_noop(tmp_path):
    env = {"X": "1"}
    assert load_dotenv_into(env, start=tmp_path) == {"X": "1"}
