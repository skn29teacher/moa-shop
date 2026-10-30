"""사용자가 명시한 전용 DB에서만 실행되는 실제 PostgreSQL 검증."""

import os
import re
from contextlib import contextmanager
from uuid import uuid4

import pytest
from psycopg import connect
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app import main
from app.core.config import Settings
from tests.legacy_security import hash_password
from tests.fake_auth import FakeAuth
from types import SimpleNamespace
from tests.support import (
    FlaskTestResponse, ORIGIN, PASSWORD, SHIPPING, add, buy_now, checkout, pay,
)


CONFIRMATION = "I_WILL_USE_A_DEDICATED_TEST_DATABASE"


class SchemaConnection:
    """애플리케이션의 public 테이블 SQL을 임시 스키마로 한정합니다."""

    def __init__(self, connection, schema):
        self.connection = connection
        self.schema = schema

    @contextmanager
    def transaction(self):
        with self.connection.transaction():
            yield

    def execute(self, query, *args, **kwargs):
        if isinstance(query, str):
            query = query.replace("public.", f'"{self.schema}".')
        return self.connection.execute(query, *args, **kwargs)


class ScopedPool:
    def __init__(self, connection_pool, schema):
        self.pool = connection_pool
        self.schema = schema

    def open(self, **kwargs):
        self.pool.open(**kwargs)

    def close(self):
        self.pool.close()

    @contextmanager
    def connection(self):
        with self.pool.connection() as connection:
            yield SchemaConnection(connection, self.schema)


def _schema_statements(schema_sql, schema):
    # 주석, public-qualified 이름, Supabase 전용 역할 REVOKE를 정리한 뒤 문장별 실행.
    text = re.sub(r"(?m)^\s*--.*$", "", schema_sql)
    text = text.replace("BEGIN;", "").replace("COMMIT;", "")
    text = re.sub(r"REVOKE ALL ON TABLE.*?FROM anon, authenticated;", "", text, flags=re.S)
    text = text.replace("public.", f'"{schema}".')
    return [statement.strip() for statement in text.split(";") if statement.strip()]


@pytest.fixture
def postgres_client():
    # 의도적으로 프로젝트 .env를 전혀 읽지 않습니다. 전용 DB를 별도 환경변수로 지정해야 합니다.
    database_url = os.environ.get("TEST_DATABASE_URL")
    if os.environ.get("RUN_DB_INTEGRATION_TESTS") != "1":
        pytest.skip("RUN_DB_INTEGRATION_TESTS=1로 설정한 경우에만 실행합니다.")
    if os.environ.get("TEST_DATABASE_CONFIRM_ISOLATED") != CONFIRMATION:
        pytest.skip("전용 테스트 DB 확인 문구가 설정되지 않았습니다.")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL이 설정되지 않았습니다.")

    schema = f"shop_test_{uuid4().hex}"
    admin = connect(database_url, autocommit=True, connect_timeout=5)
    pool = None
    try:
        admin.execute(f'CREATE SCHEMA "{schema}"')
        schema_path = main.PROJECT_ROOT / "sql" / "schema.sql"
        schema_sql = schema_path.read_text(encoding="utf-8")
        for statement in _schema_statements(schema_sql, schema):
            admin.execute(statement)

        # Apply the table portion of the auth migration in an isolated generic PG schema.
        # auth.users trigger/FK are verified separately against a Supabase test project.
        migration = (main.PROJECT_ROOT / "sql" / "auth-migration.sql").read_text(encoding="utf-8")
        migration = migration.split("-- Only profile fields")[0]
        migration = migration.replace(" REFERENCES auth.users(id) ON DELETE RESTRICT", "")
        migration = re.sub(r"REVOKE ALL ON public.auth_sessions FROM PUBLIC, anon, authenticated;", "", migration)
        for statement in _schema_statements(migration, schema):
            admin.execute(statement)

        app_settings = Settings(
            _env_file=None,
            app_origin=ORIGIN,
            database_url=database_url,
            secret_key="postgres-integration-test-secret-" * 2,
            cookie_secure=False,
            supabase_url="https://auth.invalid", supabase_key="test-anon-key",
        )
        pool = ConnectionPool(
            conninfo=database_url,
            min_size=1,
            max_size=3,
            timeout=5,
            open=False,
            kwargs={"autocommit": True, "row_factory": dict_row, "sslmode": "require",
                    "connect_timeout": 5, "prepare_threshold": None},
        )
        scoped_pool = ScopedPool(pool, schema)
        app = main.create_app(settings=app_settings, pool=scoped_pool)
        app.response_class = FlaskTestResponse
        client = app.test_client()
        client.environ_base.update(
            HTTP_HOST="127.0.0.1:8000",
            HTTP_ORIGIN=ORIGIN,
        )
        try:
            with pool.connection() as connection:
                user_id = uuid4()
                connection.execute(
                    f'INSERT INTO "{schema}".users (id,auth_user_id,email,password_hash,name) VALUES (%s,%s,%s,%s,%s)',
                    (user_id, user_id, "buyer@example.com", hash_password(PASSWORD), "통합 테스트 회원"),
                )
                connection.execute(
                    f'INSERT INTO "{schema}".products (id,name,description,price,stock) VALUES (%s,%s,%s,%s,%s)',
                    (uuid4(), "통합 테스트 상품", "", 19000, 4),
                )
            fake_store = SimpleNamespace(tokens={}, tables={'users': {user_id: {
                'id': user_id, 'auth_user_id': user_id, 'email': 'buyer@example.com',
                'password_hash': hash_password(PASSWORD),
            }}})
            app.config['auth_provider_factory'] = lambda settings: FakeAuth(fake_store)
            yield client
        finally:
            client.close()
    finally:
        if pool is not None:
            pool.close()
        admin.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        admin.close()


@pytest.mark.integration
def test_real_postgres_checkout_payment_and_idempotency(postgres_client):
    client = postgres_client
    login = client.post("/api/auth/login", json={"email": "buyer@example.com", "password": PASSWORD})
    assert login.status_code == 200, login.text
    product = client.get("/api/products")
    assert product.status_code == 200
    product_id = product.json()["items"][0]["id"]

    assert add(client, product_id, 2).status_code == 200
    order_response = checkout(client)
    assert order_response.status_code == 201, order_response.text
    order = order_response.json()
    assert order["items"][0]["product_id"] == product_id
    assert order["total_amount"] == 38_000

    paid = pay(client, order["id"], success=True)
    assert paid.status_code == 200, paid.text
    assert paid.json()["payment"]["status"] == "success"
    again = pay(client, order["id"], success=True)
    assert again.status_code == 200
    assert again.json()["already_paid"] is True

    history = client.get(f"/api/orders/{order['id']}")
    assert history.status_code == 200
    assert history.json()["status"] == "paid"
    inventory = client.get(f"/api/products/{product_id}").json()
    assert inventory["stock"] == 2
