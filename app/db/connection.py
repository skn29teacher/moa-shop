from flask import current_app, g
from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.core.config import Settings


def create_pool(settings: Settings) -> ConnectionPool:
    return ConnectionPool(
        conninfo=settings.database_url.get_secret_value(),
        min_size=1,
        max_size=5,
        timeout=5,
        open=False,
        kwargs={
            # 인증 SELECT가 암묵적 트랜잭션을 열지 않도록 합니다.
            # 변경 작업은 서비스의 connection.transaction()에서 명시적으로 커밋합니다.
            "autocommit": True,
            "row_factory": dict_row,
            "connect_timeout": 5,
            "sslmode": "require",
            # Supabase pooler에서도 서버측 prepared statement 충돌을 피합니다.
            "prepare_threshold": None,
        },
        check=ConnectionPool.check_connection,
    )


def get_connection() -> Connection:
    # 연결 수명만 관리합니다. 변경 트랜잭션은 각 서비스에서 응답 전에 완료합니다.
    if "db_connection" not in g:
        manager = current_app.config["db_pool"].connection()
        connection = manager.__enter__()
        g.db_connection_manager = manager
        g.db_connection = connection
    return g.db_connection


def close_connection(_error: BaseException | None = None) -> None:
    manager = g.pop("db_connection_manager", None)
    g.pop("db_connection", None)
    if manager is not None:
        if _error is None:
            manager.__exit__(None, None, None)
        else:
            manager.__exit__(type(_error), _error, _error.__traceback__)
