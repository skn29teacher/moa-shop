"""Request-scoped SQLite connections and explicit atomic transactions."""
import sqlite3
from contextlib import contextmanager
from uuid import UUID

from flask import current_app, g

from app.core.config import PROJECT_ROOT, Settings


ID_COLUMNS = {"id", "auth_user_id", "user_id", "order_id", "product_id"}
SCHEMA_VERSION = 1


def dict_row(cursor, values):
    return {
        column[0]: UUID(value) if column[0] in ID_COLUMNS and value is not None else value
        for column, value in zip(cursor.description, values)
    }


class Connection:
    def __init__(self, path):
        self.raw = sqlite3.connect(path, timeout=15, isolation_level=None)
        self.raw.row_factory = dict_row
        # Enable foreign keys per connection; keep default journaling without forcing WAL.
        self.raw.execute("PRAGMA foreign_keys = ON")
        self.raw.execute("PRAGMA busy_timeout = 15000")

    def execute(self, sql, parameters=()):
        values = tuple(str(value) if isinstance(value, UUID) else value for value in parameters)
        return self.raw.execute(sql, values)

    @contextmanager
    def transaction(self):
        # Reserve the writer before reading stock/cart/payment state. Commit before responding.
        if self.raw.in_transaction:
            raise RuntimeError("Nested database transactions are not supported.")
        self.raw.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.raw.commit()
        except BaseException:
            self.raw.rollback()
            raise

    def close(self):
        self.raw.close()


class SQLiteDatabase:
    """Connection factory; connections are never shared between requests or threads."""
    def __init__(self, path):
        self.path = path

    def open(self, **_kwargs):
        if sqlite3.sqlite_version_info < (3, 35, 0):
            raise RuntimeError("SQLite 3.35 이상이 필요합니다. Python 런타임을 업그레이드하세요.")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as connection:
            # Serialize first startup so multiple WSGI workers cannot initialize twice.
            with connection.transaction():
                version = connection.execute("PRAGMA user_version").fetchone()['user_version']
                if version == 0:
                    existing = connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                    ).fetchall()
                    if existing:
                        raise RuntimeError("기존 SQLite 스키마를 확인하세요. 빈 DB 파일 또는 지원 버전이 필요합니다.")
                    schema = (PROJECT_ROOT / "sql" / "schema.sql").read_text(encoding="utf-8")
                    # executescript implicitly commits; execute statements individually instead.
                    statement = ""
                    for line in schema.splitlines(keepends=True):
                        statement += line
                        if sqlite3.complete_statement(statement):
                            connection.execute(statement)
                            statement = ""
                    if statement.strip():
                        raise RuntimeError("Incomplete SQLite schema statement.")
                    connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
                elif version != SCHEMA_VERSION:
                    raise RuntimeError("지원하지 않는 SQLite 스키마 버전입니다.")

    @contextmanager
    def connection(self):
        connection = Connection(self.path)
        try:
            yield connection
        finally:
            connection.close()

    def close(self):
        pass  # No persistent pool or background connection threads.


def create_pool(settings: Settings) -> SQLiteDatabase:
    return SQLiteDatabase(settings.database_path)


def get_connection() -> Connection:
    if "db_connection" not in g:
        manager = current_app.config["db_pool"].connection()
        g.db_connection = manager.__enter__()
        g.db_connection_manager = manager
    return g.db_connection


def close_connection(_error: BaseException | None = None) -> None:
    manager = g.pop("db_connection_manager", None)
    g.pop("db_connection", None)
    if manager is not None:
        manager.__exit__(None, None, None)
