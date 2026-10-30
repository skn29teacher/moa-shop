"""Real SQLite SQL/constraints/transactions; only Supabase HTTPS is substituted."""
import json
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID, uuid4

import pytest

from app.core.config import Settings
from app.core.security import AUTH_COOKIE_NAME
from app.db import commerce, users
from app.db.connection import Connection, SQLiteDatabase
from app.main import create_app
from app.services import payments
from app.services.sessions import cipher, digest
from tests.fake_auth import FakeAuth
from tests.memory import MemoryStore
from tests.support import (
    FlaskTestResponse, ORIGIN, PASSWORD, USER_A, USER_B, P1, P2, SOLD_OUT,
    add, buy_now, checkout, pay,
)


@pytest.fixture
def sqlite_app(tmp_path, password_hash):
    settings = Settings(
        _env_file=None, database_path=tmp_path / 'shop.sqlite3', app_origin=ORIGIN,
        secret_key='sqlite-test-only-secret-' * 3,
        supabase_url='https://auth.invalid', supabase_key='test-anon-key',
    )
    # This store represents Auth accounts, not shopping data or database functions.
    auth_store = MemoryStore(password_hash)
    auth_store.tokens = {}
    for user in auth_store.tables['users'].values():
        user.update(auth_user_id=user['id'], role='customer')
    fake = FakeAuth(auth_store)
    app = create_app(settings)
    app.config['auth_provider_factory'] = lambda _: fake
    app.config['fake_auth'] = fake
    app.response_class = FlaskTestResponse
    with app.config['db_pool'].connection() as connection:
        with connection.transaction():
            for uid, name, price, stock in [(P1, '티셔츠', 19000, 10), (P2, '가방', 15000, 5), (SOLD_OUT, '품절', 5000, 0)]:
                connection.execute('INSERT INTO products (id,name,price,stock) VALUES (?,?,?,?)', (uid, name, price, stock))
    return app


def client_for(app):
    client = app.test_client()
    client.environ_base.update(HTTP_HOST='127.0.0.1:8000', HTTP_ORIGIN=ORIGIN)
    return client


def sign_in(app, email='buyer@example.com', password=PASSWORD):
    client = client_for(app)
    response = client.post('/api/auth/login', json={'email': email, 'password': password})
    assert response.status_code == 200, response.text
    return client


def fetch_one(app, sql, values=()):
    with app.config['db_pool'].connection() as connection:
        return connection.execute(sql, values).fetchone()


def execute(app, sql, values=()):
    with app.config['db_pool'].connection() as connection:
        with connection.transaction():
            connection.execute(sql, values)


@pytest.mark.integration
def test_first_login_creates_local_profile_and_does_not_store_password(sqlite_app):
    app = sqlite_app
    assert fetch_one(app, 'SELECT count(*) AS n FROM users')['n'] == 0
    client = sign_in(app)
    profile = client.get('/api/members/me').json()
    assert profile['id'] == str(USER_A) and profile['role'] == 'customer'
    with app.config['db_pool'].connection() as connection:
        names = {row['name'] for row in connection.execute('PRAGMA table_info(users)').fetchall()}
    assert 'password' not in names and 'password_hash' not in names
    row = fetch_one(app, 'SELECT * FROM auth_sessions')
    assert row['encrypted_tokens'] and 'access_token' not in row['encrypted_tokens']
    assert fetch_one(app, 'SELECT count(*) AS n FROM users')['n'] == 1


@pytest.mark.integration
def test_signup_waits_for_verified_login_before_local_profile_creation(sqlite_app):
    app = sqlite_app
    client = client_for(app)
    response = client.post('/api/auth/signup', json={
        'email': 'new@example.com', 'password': PASSWORD, 'name': '새 회원',
        'phone': '010-1234-5678', 'address': '서울',
    })
    assert response.status_code == 202
    assert fetch_one(app, 'SELECT count(*) AS n FROM users')['n'] == 0
    assert client.post('/api/auth/login', json={'email': 'new@example.com', 'password': 'wrong'}).status_code == 401
    assert fetch_one(app, 'SELECT count(*) AS n FROM users')['n'] == 0
    client = sign_in(app, 'new@example.com')
    profile = client.get('/api/members/me').json()
    assert (profile['name'], profile['phone'], profile['address']) == ('새 회원', '010-1234-5678', '서울')


@pytest.mark.integration
def test_concurrent_first_logins_create_one_profile(sqlite_app):
    app = sqlite_app
    gate = Barrier(2)
    def login(_):
        gate.wait(timeout=10)
        return sign_in(app).get('/api/members/me').status_code
    with ThreadPoolExecutor(max_workers=2) as executor:
        assert list(executor.map(login, range(2))) == [200, 200]
    assert fetch_one(app, 'SELECT count(*) AS n FROM users')['n'] == 1
    assert fetch_one(app, 'SELECT count(*) AS n FROM auth_sessions')['n'] == 2


@pytest.mark.integration
def test_ordinary_auth_lookup_does_not_hold_the_sqlite_writer_lock(sqlite_app, monkeypatch):
    app = sqlite_app
    buyer = sign_in(app)
    original = app.config['fake_auth'].user
    def verify(token):
        # A different connection can write while the Auth HTTP boundary is in progress.
        with app.config['db_pool'].connection() as connection:
            connection.execute('PRAGMA busy_timeout = 50')
            with connection.transaction():
                connection.execute('UPDATE products SET description=description WHERE id=?', (P1,))
        return original(token)
    monkeypatch.setattr(app.config['fake_auth'], 'user', verify)
    assert buyer.get('/api/members/me').status_code == 200


@pytest.mark.integration
def test_untrusted_metadata_cannot_grant_role_or_overwrite_local_profile(sqlite_app, monkeypatch):
    app = sqlite_app
    original = app.config['fake_auth'].issue
    def malicious(uid):
        result = original(uid)
        result['user']['user_metadata'].update(role='admin', name='유효 이름', phone=['invalid'])
        result['user']['app_metadata'] = {'role': 'admin'}
        return result
    monkeypatch.setattr(app.config['fake_auth'], 'issue', malicious)
    client = sign_in(app)
    assert client.get('/api/members/me').json()['role'] == 'customer'
    assert client.get('/api/members/me').json()['phone'] is None
    assert client.patch('/api/members/me', json={'name': '로컬 이름'}).status_code == 200
    client = sign_in(app)
    assert client.get('/api/members/me').json()['name'] == '로컬 이름'
    assert client.get('/api/admin/orders').status_code == 403


@pytest.mark.integration
def test_existing_email_is_not_automatically_linked_to_another_identity(sqlite_app):
    app = sqlite_app
    different = uuid4()
    execute(app, 'INSERT INTO users (id,auth_user_id,email,name,role) VALUES (?,?,?,?,?)',
            (different, different, 'buyer@example.com', '기존 관리자', 'admin'))
    client = client_for(app)
    assert client.post('/api/auth/login', json={'email': 'buyer@example.com', 'password': PASSWORD}).status_code == 409
    assert fetch_one(app, 'SELECT auth_user_id FROM users')['auth_user_id'] == different


@pytest.mark.integration
def test_native_checkout_payment_ownership_and_restart_persistence(sqlite_app):
    app = sqlite_app
    buyer = sign_in(app)
    assert add(buyer, P1, 2).status_code == 200
    assert add(buyer, P1, 1).json()['items'][0]['quantity'] == 3
    order = checkout(buyer).json()
    other = sign_in(app, 'other@example.com')
    assert other.get('/api/orders/' + order['id']).status_code == 404
    assert pay(other, order['id']).status_code == 404
    assert pay(buyer, order['id']).json()['already_paid'] is False
    assert pay(buyer, order['id']).json()['already_paid'] is True
    assert fetch_one(app, 'SELECT stock FROM products WHERE id=?', (P1,))['stock'] == 7
    assert fetch_one(app, "SELECT count(*) AS n FROM payments WHERE status='success'")['n'] == 1
    restarted = create_app(app.config['settings'])
    restarted.config['auth_provider_factory'] = app.config['auth_provider_factory']
    restarted.response_class = FlaskTestResponse
    reopened = client_for(restarted)
    reopened.set_cookie(AUTH_COOKIE_NAME, buyer.get_cookie(AUTH_COOKIE_NAME).value)
    assert reopened.get('/api/orders/' + order['id']).json()['status'] == 'paid'


@pytest.mark.integration
def test_native_cart_edit_failure_payment_and_checkout_rollback(sqlite_app):
    app = sqlite_app
    client = sign_in(app)
    assert add(client, P1, 2).status_code == 200
    assert add(client, P2, 1).status_code == 200
    changed = client.patch(f'/api/cart/items/{P1}', json={'quantity': 3})
    assert changed.json()['total_amount'] == 72000
    assert client.delete(f'/api/cart/items/{P2}').json()['total_amount'] == 57000
    assert add(client, SOLD_OUT).status_code == 409
    assert fetch_one(app, 'SELECT count(*) AS n FROM order_items')['n'] == 1
    order = checkout(client).json()
    assert pay(client, order['id'], success=False).json()['payment']['status'] == 'failed'
    assert fetch_one(app, 'SELECT stock FROM products WHERE id=?', (P1,))['stock'] == 10
    assert pay(client, order['id'], success=True).status_code == 200


@pytest.mark.integration
def test_native_late_payment_error_rolls_back_stock_and_payment(sqlite_app, monkeypatch):
    app = sqlite_app
    client = sign_in(app)
    order = buy_now(client, P1, 2).json()
    original = payments.decrease_stock
    def fail_after_mutation(connection, pid, quantity):
        original(connection, pid, quantity)
        raise sqlite3.OperationalError('simulated failure')
    monkeypatch.setattr(payments, 'decrease_stock', fail_after_mutation)
    assert pay(client, order['id']).status_code == 503
    assert fetch_one(app, 'SELECT stock FROM products WHERE id=?', (P1,))['stock'] == 10
    assert fetch_one(app, 'SELECT count(*) AS n FROM payments')['n'] == 0
    assert fetch_one(app, 'SELECT status FROM orders')['status'] == 'pending'


def pay_concurrently(app, work):
    gate = Barrier(len(work))
    def worker(pair):
        uid, oid = pair
        with app.config['db_pool'].connection() as connection:
            gate.wait(timeout=10)
            return payments.pay_order(connection, uid, UUID(oid), True)
    with ThreadPoolExecutor(max_workers=len(work)) as executor:
        return list(executor.map(worker, work))


@pytest.mark.integration
def test_two_buyers_cannot_oversell_last_item(sqlite_app):
    app = sqlite_app
    buyer = sign_in(app)
    other = sign_in(app, 'other@example.com')
    execute(app, 'UPDATE products SET stock=1 WHERE id=?', (P1,))
    one = buy_now(buyer, P1, 1).json()['id']
    two = buy_now(other, P1, 1).json()['id']
    results = pay_concurrently(app, [(USER_A, one), (USER_B, two)])
    assert sorted(code for _, code in results) == [200, 409]
    assert fetch_one(app, 'SELECT stock FROM products WHERE id=?', (P1,))['stock'] == 0
    assert fetch_one(app, "SELECT count(*) AS n FROM payments WHERE status='success'")['n'] == 1
    assert fetch_one(app, "SELECT count(*) AS n FROM payments WHERE status='failed'")['n'] == 1


@pytest.mark.integration
def test_concurrent_retries_of_one_payment_decrement_stock_once(sqlite_app):
    app = sqlite_app
    buyer = sign_in(app)
    oid = buy_now(buyer, P1, 2).json()['id']
    results = pay_concurrently(app, [(USER_A, oid), (USER_A, oid)])
    assert sorted(result['already_paid'] for result, _ in results) == [False, True]
    assert fetch_one(app, 'SELECT stock FROM products WHERE id=?', (P1,))['stock'] == 8
    assert fetch_one(app, 'SELECT count(*) AS n FROM payments')['n'] == 1


@pytest.mark.integration
def test_concurrent_refresh_rotates_provider_token_once(sqlite_app, monkeypatch):
    app = sqlite_app
    buyer = sign_in(app)
    value = buyer.get_cookie(AUTH_COOKIE_NAME).value
    row = fetch_one(app, 'SELECT encrypted_tokens FROM auth_sessions WHERE token_hash=?', (digest(value),))
    with app.app_context():
        tokens = json.loads(cipher().decrypt(row['encrypted_tokens'].encode()))
        tokens['expires_at'] = time.time() - 1
        encrypted = cipher().encrypt(json.dumps(tokens).encode()).decode()
    execute(app, 'UPDATE auth_sessions SET encrypted_tokens=? WHERE token_hash=?', (encrypted, digest(value)))
    original = app.config['fake_auth'].refresh
    calls = []
    def refresh(token):
        calls.append(token)
        return original(token)
    monkeypatch.setattr(app.config['fake_auth'], 'refresh', refresh)
    gate = Barrier(2)
    def request(_):
        client = client_for(app)
        client.set_cookie(AUTH_COOKIE_NAME, value)
        gate.wait(timeout=10)
        return client.get('/api/members/me').status_code
    with ThreadPoolExecutor(max_workers=2) as executor:
        assert list(executor.map(request, range(2))) == [200, 200]
    assert len(calls) == 1


@pytest.mark.integration
def test_sqlite_constraints_foreign_keys_and_rollback(sqlite_app):
    app = sqlite_app
    sign_in(app)
    with app.config['db_pool'].connection() as connection:
        assert connection.execute('PRAGMA foreign_keys').fetchone()['foreign_keys'] == 1
        with pytest.raises(sqlite3.IntegrityError):
            with connection.transaction():
                commerce.insert_cart(connection, USER_A)
                commerce.insert_cart(connection, USER_A)
        assert connection.execute('SELECT count(*) AS n FROM orders').fetchone()['n'] == 0
        with pytest.raises(sqlite3.IntegrityError):
            with connection.transaction():
                commerce.insert_cart(connection, uuid4())
        with pytest.raises(sqlite3.IntegrityError):
            with connection.transaction():
                connection.execute('UPDATE products SET stock=-1 WHERE id=?', (P1,))


@pytest.mark.integration
def test_native_admin_roles_product_operations_and_revocation(sqlite_app):
    app = sqlite_app
    buyer = sign_in(app)
    assert buyer.get('/api/admin/orders').status_code == 403
    runner = app.test_cli_runner()
    result = runner.invoke(args=['set-role', '--auth-user-id', str(USER_A), '--role', 'admin'])
    assert result.exit_code == 0, result.output
    body = {'name': '관리 상품', 'description': '설명', 'price': 9000, 'stock': 2}
    created = buyer.post('/api/admin/products', json=body)
    assert created.status_code == 201, created.text
    assert buyer.put('/api/admin/products/' + created.json()['id'], json={**body, 'stock': 1}).json()['stock'] == 1
    other = sign_in(app, 'other@example.com')
    order = buy_now(other, P1, 1).json()
    assert buyer.get('/api/admin/orders').json()[0]['id'] == order['id']
    assert runner.invoke(args=['set-role', '--auth-user-id', str(USER_A), '--role', 'customer']).exit_code == 0
    assert buyer.get('/api/admin/orders').status_code == 403


@pytest.mark.integration
def test_local_session_expiry_logout_and_password_revocation(sqlite_app):
    app = sqlite_app
    buyer = sign_in(app)
    value = buyer.get_cookie(AUTH_COOKIE_NAME).value
    execute(app, 'UPDATE auth_sessions SET expires_at=0')
    assert buyer.get('/api/members/me').status_code == 401
    buyer = sign_in(app)
    value = buyer.get_cookie(AUTH_COOKIE_NAME).value
    assert buyer.post('/api/auth/logout').status_code == 204
    buyer.set_cookie(AUTH_COOKIE_NAME, value)
    assert buyer.get('/api/cart').status_code == 401
    buyer = sign_in(app)
    second = sign_in(app)
    assert buyer.put('/api/members/me/password', json={
        'current_password': PASSWORD, 'new_password': 'New-password-2026!',
    }).status_code == 204
    assert second.get('/api/cart').status_code == 401
    assert fetch_one(app, 'SELECT count(*) AS n FROM auth_sessions')['n'] == 0
    assert sign_in(app, password='New-password-2026!').get('/api/cart').status_code == 200


@pytest.mark.integration
def test_deleted_profile_cannot_be_recreated_by_login(sqlite_app):
    app = sqlite_app
    buyer = sign_in(app)
    oid = buy_now(buyer, P1, 1).json()['id']
    assert buyer.delete('/api/members/me').status_code == 204
    assert buyer.post('/api/auth/login', json={'email': 'buyer@example.com', 'password': PASSWORD}).status_code == 401
    assert fetch_one(app, 'SELECT count(*) AS n FROM users')['n'] == 1
    assert fetch_one(app, 'SELECT id FROM orders')['id'] == UUID(oid)


@pytest.mark.integration
def test_initialization_and_seed_are_repeatable_without_resetting_stock(sqlite_app):
    app = sqlite_app
    runner = app.test_cli_runner()
    assert runner.invoke(args=['init-db']).exit_code == 0
    assert runner.invoke(args=['seed-demo']).exit_code == 0
    sample = UUID('10000000-0000-4000-8000-000000000001')
    execute(app, 'UPDATE products SET stock=1 WHERE id=?', (sample,))
    result = runner.invoke(args=['seed-demo'])
    assert result.exit_code == 0, result.output
    create_app(app.config['settings'])
    assert fetch_one(app, 'SELECT stock FROM products WHERE id=?', (sample,))['stock'] == 1
    assert fetch_one(app, 'SELECT count(*) AS n FROM products')['n'] == 8


@pytest.mark.integration
def test_unknown_existing_database_is_not_silently_overwritten(tmp_path):
    path = tmp_path / 'unknown.sqlite3'
    raw = sqlite3.connect(path)
    raw.execute('CREATE TABLE important_data (value TEXT)')
    raw.commit()
    raw.close()
    with pytest.raises(RuntimeError, match='기존 SQLite'):
        SQLiteDatabase(path).open()
    raw = sqlite3.connect(path)
    assert raw.execute("SELECT count(*) FROM sqlite_master WHERE name='important_data'").fetchone()[0] == 1
    raw.close()
