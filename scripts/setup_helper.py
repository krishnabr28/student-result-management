"""Helper for setup.bat: checks the MySQL login and writes the settings into .env.

The MySQL password is read from the SRMS_DB_SECRET environment variable so it never appears on a command line.
"""

import argparse
import os
import secrets
import sys
from pathlib import Path

import mysql.connector
from dotenv import dotenv_values
from mysql.connector import errorcode

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"
EXAMPLE_FILE = ROOT / ".env.example"
SECRET_VAR = "SRMS_DB_SECRET"  # noqa: S105 (name of the variable, not a value)
LOCAL_HOST = "127.0.0.1"

OK, FAILED, WRONG_LOGIN, UNREACHABLE = 0, 1, 2, 3


def check_login(host, port, user, password):
    try:
        mysql.connector.connect(host=host, port=port, user=user, password=password, connection_timeout=5).close()
    except mysql.connector.Error as exc:
        if exc.errno in (errorcode.ER_ACCESS_DENIED_ERROR, errorcode.ER_ACCESS_DENIED_NO_PASSWORD_ERROR):
            return WRONG_LOGIN, "MySQL says this password is wrong."
        return UNREACHABLE, f"Could not reach MySQL at {host}:{port}: {exc.msg}"
    return OK, ""


def dotenv_quote(value):
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def update_env(env_file, example_file, values):
    source = env_file if env_file.exists() else example_file
    written = set()
    lines = []
    for line in source.read_text(encoding="utf-8").splitlines():
        key = line.split("=", 1)[0].strip()
        if "=" in line and not line.lstrip().startswith("#") and key in values:
            if key in written:
                continue
            line = f"{key}={values[key]}"
            written.add(key)
        lines.append(line)
    lines += [f"{key}={value}" for key, value in values.items() if key not in written]
    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def ensure_env(env_file, example_file):
    current = dotenv_values(env_file, interpolate=False) if env_file.exists() else {}
    secret_key = current.get("SECRET_KEY") or ""
    if not secret_key or secret_key.startswith("change-me"):
        update_env(env_file, example_file, {"SECRET_KEY": secrets.token_hex(32)})
    elif not env_file.exists():
        update_env(env_file, example_file, {})


def env_login_works(env_file):
    if not env_file.exists():
        return False
    config = dotenv_values(env_file, interpolate=False)
    if not config.get("DB_USER"):
        return False
    try:
        port = int(config.get("DB_PORT") or 3306)
    except ValueError:
        return False
    host = config.get("DB_HOST") or "localhost"
    status, _ = check_login(host, port, config["DB_USER"], config.get("DB_PASSWORD") or "")
    return status == OK


def set_root_password(port, new_password):
    connection = mysql.connector.connect(host=LOCAL_HOST, port=port, user="root", password="", connection_timeout=10)
    try:
        cursor = connection.cursor()
        cursor.execute("ALTER USER CURRENT_USER() IDENTIFIED BY %s", (new_password,))
        cursor.close()
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["env-ok", "check", "set-root", "save", "ensure-env"])
    parser.add_argument("--port", type=int, default=3306)
    args = parser.parse_args()
    password = os.environ.get(SECRET_VAR, "")

    if args.command == "env-ok":
        return OK if env_login_works(ENV_FILE) else FAILED

    if args.command == "check":
        status, message = check_login(LOCAL_HOST, args.port, "root", password)
        if message:
            print(f"    {message}")
        return status

    if args.command == "set-root":
        if not password:
            print("    No password given.")
            return FAILED
        try:
            set_root_password(args.port, password)
        except mysql.connector.Error as exc:
            print(f"    Could not set the MySQL root password: {exc.msg}")
            return FAILED
        return OK

    if args.command == "save":
        values = {"DB_HOST": LOCAL_HOST, "DB_PORT": str(args.port), "DB_USER": "root"}
        values["DB_PASSWORD"] = dotenv_quote(password)
        update_env(ENV_FILE, EXAMPLE_FILE, values)

    ensure_env(ENV_FILE, EXAMPLE_FILE)
    return OK


if __name__ == "__main__":
    sys.exit(main())
