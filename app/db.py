from contextlib import contextmanager

import mysql.connector
from flask import current_app, g


class DatabaseUnavailable(Exception):
    pass


def get_connection():
    """One connection per request, closed in close_connection()."""
    if "db" not in g:
        try:
            g.db = mysql.connector.connect(
                **current_app.config["DB"],
                autocommit=True,
                connection_timeout=5,
                charset="utf8mb4",
                collation="utf8mb4_unicode_ci",
                time_zone="+00:00",
            )
        except mysql.connector.Error as exc:
            raise DatabaseUnavailable(str(exc)) from exc
    return g.db


def close_connection(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def execute_query(sql, params=(), *, fetch=None):
    """Run a parameterised query. fetch: None | 'one' | 'all'. Returns rows, or lastrowid when fetch is None."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True, buffered=True)
    try:
        cursor.execute(sql, params)
        if fetch == "one":
            return cursor.fetchone()
        if fetch == "all":
            return cursor.fetchall()
        return cursor.lastrowid
    finally:
        cursor.close()


def fetch_one(sql, params=()):
    return execute_query(sql, params, fetch="one")


def fetch_all(sql, params=()):
    return execute_query(sql, params, fetch="all")


@contextmanager
def transaction():
    """Group several statements so they all succeed or all roll back."""
    conn = get_connection()
    conn.start_transaction()
    cursor = conn.cursor(dictionary=True, buffered=True)
    try:
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
