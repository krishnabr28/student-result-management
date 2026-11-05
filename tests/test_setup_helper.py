import pytest
from dotenv import dotenv_values

from scripts.setup_helper import dotenv_quote, ensure_env, update_env

EXAMPLE = """# comment DB_PASSWORD=not-this
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your-mysql-password
SECRET_KEY=change-me-to-a-long-random-value
APP_PORT=5000
"""


@pytest.fixture
def files(tmp_path):
    example = tmp_path / ".env.example"
    example.write_text(EXAMPLE, encoding="utf-8")
    return tmp_path / ".env", example


@pytest.mark.parametrize("secret", ["simple123", 'it\'s \\ tricky #1 ${HOME} "quoted" = ok', "", "  spaced  "])
def test_saved_password_reads_back_exactly(files, secret):
    env, example = files
    update_env(env, example, {"DB_HOST": "127.0.0.1", "DB_PASSWORD": dotenv_quote(secret)})
    values = dotenv_values(env, interpolate=False)
    assert values["DB_PASSWORD"] == secret
    assert values["DB_HOST"] == "127.0.0.1"
    assert values["APP_PORT"] == "5000"
    assert env.read_text(encoding="utf-8").startswith("# comment DB_PASSWORD=not-this\n")


def test_ensure_env_creates_file_with_random_secret_once(files):
    env, example = files
    ensure_env(env, example)
    first = dotenv_values(env)["SECRET_KEY"]
    assert len(first) == 64 and not first.startswith("change-me")
    ensure_env(env, example)
    assert dotenv_values(env)["SECRET_KEY"] == first


def test_update_keeps_existing_settings_and_appends_missing(files):
    env, example = files
    env.write_text("APP_PORT=5050\nSECRET_KEY=keep-me\n", encoding="utf-8")
    update_env(env, example, {"DB_USER": "root"})
    ensure_env(env, example)
    values = dotenv_values(env)
    assert values == {"APP_PORT": "5050", "SECRET_KEY": "keep-me", "DB_USER": "root"}


def test_duplicate_keys_collapse_to_the_saved_value(files):
    env, example = files
    env.write_text("DB_PASSWORD=old\nAPP_PORT=5000\nDB_PASSWORD=older\n", encoding="utf-8")
    update_env(env, example, {"DB_PASSWORD": dotenv_quote("new")})
    assert env.read_text(encoding="utf-8") == "DB_PASSWORD='new'\nAPP_PORT=5000\n"
