import re

import mysql.connector
import pytest

import setup_db
from app import create_app
from app.config import load_config

TEST_DB = "srms_test"


def _server_config():
    config = dict(load_config()["DB"])
    config["database"] = TEST_DB
    return config


@pytest.fixture(scope="session")
def db_config():
    config = _server_config()
    try:
        conn = setup_db.connect(config)
    except mysql.connector.Error as exc:
        pytest.skip(f"MySQL not reachable with the settings in .env: {exc}")
    cur = conn.cursor()
    cur.execute(f"DROP DATABASE IF EXISTS `{TEST_DB}`")
    cur.execute(f"CREATE DATABASE `{TEST_DB}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    cur.execute(f"USE `{TEST_DB}`")
    setup_db.create_schema(cur)
    conn.close()
    yield config
    conn = setup_db.connect(config)
    conn.cursor().execute(f"DROP DATABASE IF EXISTS `{TEST_DB}`")
    conn.close()


@pytest.fixture
def db(db_config):
    """Fresh demo data for every test."""
    conn = setup_db.connect(db_config, TEST_DB)
    cur = conn.cursor()
    cur.execute("SET FOREIGN_KEY_CHECKS = 0")
    for table in ("notification_reads", "notifications", "results", "students", "users"):
        cur.execute(f"TRUNCATE TABLE {table}")
    cur.execute("SET FOREIGN_KEY_CHECKS = 1")
    conn.start_transaction()
    setup_db.seed_demo(cur)
    conn.commit()
    yield cur
    conn.close()


@pytest.fixture
def app(db_config, db):
    return create_app({"TESTING": True, "SECRET_KEY": "test-secret", "DB": db_config, "SHOW_DEMO_ACCOUNTS": True})


@pytest.fixture
def client(app):
    return app.test_client()


def csrf_from(response):
    match = re.search(r'name="csrf-token" content="([^"]+)"', response.get_data(as_text=True))
    assert match, "CSRF meta tag missing"
    return match.group(1)


class Browser:
    """Small helper that keeps the CSRF token like a real browser form would."""

    def __init__(self, client):
        self.client = client
        self.token = csrf_from(client.get("/login"))

    def get(self, url, **kw):
        return self.client.get(url, **kw)

    def post(self, url, data=None, **kw):
        data = dict(data or {})
        data.setdefault("csrf_token", self.token)
        return self.client.post(url, data=data, **kw)

    def login(self, username, password):
        return self.post("/login", {"username": username, "password": password})

    def logout(self):
        response = self.post("/logout")
        self.token = csrf_from(self.client.get("/login"))
        return response


@pytest.fixture
def browser(client):
    return Browser(client)


def query(db, sql, params=()):
    db.execute(sql, params)
    return db.fetchall()
