"""PostgreSQL: пул соединений, транзакции, миграции.
Соединение в autocommit; изменения группируются в `with db.transaction():`. Строки — словари."""
from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from . import config

MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"
_pool = None


def pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(config.DSN, min_size=1, max_size=10, open=True,
                               kwargs={"autocommit": True, "row_factory": dict_row})
    return _pool


def close_pool():
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


@contextmanager
def connect():
    with pool().connection() as conn:
        yield conn


def direct(dsn=None):
    return psycopg.connect(dsn or config.DSN, autocommit=True, row_factory=dict_row)


def migrate(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())")
    done = {r["name"] for r in conn.execute("SELECT name FROM schema_migrations")}
    for path in sorted(MIGRATIONS.glob("*.sql")):
        if path.name in done:
            continue
        with conn.transaction():
            conn.execute(path.read_text(encoding="utf-8"))
            conn.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (path.name,))
