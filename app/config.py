import os
import secrets

from dotenv import load_dotenv

load_dotenv(interpolate=False)


def _require(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing setting {name}. Copy .env.example to .env and fill it in (see README).")
    return value


def load_config():
    secret_key = os.environ.get("SECRET_KEY")
    if not secret_key or secret_key.startswith("change-me"):
        # Sessions reset on every restart without a fixed key; fine for a first run, warned in README.
        secret_key = secrets.token_hex(32)
    return {
        "SECRET_KEY": secret_key,
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "PERMANENT_SESSION_LIFETIME": 60 * 60 * 8,
        "MAX_CONTENT_LENGTH": 1024 * 1024,
        "SHOW_DEMO_ACCOUNTS": os.environ.get("SHOW_DEMO_ACCOUNTS", "false").lower() in ("1", "true", "yes"),
        "DB": {
            "host": os.environ.get("DB_HOST", "localhost"),
            "port": int(os.environ.get("DB_PORT", "3306")),
            "user": _require("DB_USER"),
            "password": os.environ.get("DB_PASSWORD", ""),
            "database": os.environ.get("DB_NAME", "internship_result_db"),
        },
    }
