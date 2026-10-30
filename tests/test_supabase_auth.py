import json
import time
from types import SimpleNamespace
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest
from pydantic import SecretStr

from app.core.errors import HTTPException
from app.core.security import AUTH_COOKIE_NAME
from app.core.supabase_auth import SupabaseAuth
from app.schemas.auth import SignupRequest
from app.services.sessions import cipher, digest
from tests.fake_auth import FakeAuth
from tests.memory import MemoryConnection
from tests.support import PASSWORD, P1, USER_A, USER_B, authorize


def test_signup_uses_application_origin_for_email_confirmation(monkeypatch):
    settings = SimpleNamespace(
        supabase_url='https://auth.example.test',
        supabase_key=SecretStr('test-anon-key'),
        app_origin='http://127.0.0.1:8000',
    )
    auth = SupabaseAuth(settings)
    calls = []
    monkeypatch.setattr(auth, 'call', lambda method, path, body: calls.append((method, path, body)) or {})
    payload = SignupRequest(email='buyer@example.com', password=PASSWORD, name='Buyer')

    auth.signup(payload)

    method, path, body = calls[0]
    assert method == 'POST'
    assert urlsplit(path).path == '/signup'
    assert parse_qs(urlsplit(path).query) == {'redirect_to': ['http://127.0.0.1:8000/']}
    assert body['email'] == 'buyer@example.com'


def login(client):
    response = client.post('/api/auth/login', json={'email': 'buyer@example.com', 'password': PASSWORD})
    assert response.status_code == 200, response.text
    return client.get_cookie(AUTH_COOKIE_NAME).value


def test_provider_tokens_are_encrypted_and_cookie_is_an_opaque_secret(client, store):
    value = login(client)
    assert len(value) >= 40
    assert '.' not in value
    row = store.sessions[digest(value)]
    assert value not in row['encrypted_tokens']
    assert 'access_token' not in row['encrypted_tokens']
    with client.application.app_context():
        tokens = json.loads(cipher().decrypt(row['encrypted_tokens'].encode()))
    assert tokens['access_token'] in store.tokens
    assert client.get('/api/members/me').json()['role'] == 'customer'


def test_copied_cookie_is_revoked_immediately_on_logout(client, store):
    value = login(client)
    assert client.post('/api/auth/logout').status_code == 204
    assert digest(value) not in store.sessions
    client.set_cookie(AUTH_COOKIE_NAME, value)
    assert client.get('/api/members/me').status_code == 401


def test_logout_revokes_locally_during_supabase_outage(client, store, monkeypatch):
    value = login(client)
    def down(*args):
        raise HTTPException(status_code=503, detail='provider down')
    monkeypatch.setattr(FakeAuth, 'logout', down)
    assert client.post('/api/auth/logout').status_code == 204
    assert digest(value) not in store.sessions


def test_cookie_tampering_and_old_self_signed_tokens_are_rejected(client):
    for token in ('header.payload.signature', 'forged-cookie', 'x' * 300):
        client.set_cookie(AUTH_COOKIE_NAME, token)
        assert client.get('/api/cart').status_code == 401


def test_expiring_token_refreshes_once_and_persists_rotated_tokens(client, store, monkeypatch):
    value = login(client)
    row = store.sessions[digest(value)]
    with client.application.app_context():
        tokens = json.loads(cipher().decrypt(row['encrypted_tokens'].encode()))
        old_refresh = tokens['refresh_token']
        tokens['expires_at'] = time.time() - 1
        row['encrypted_tokens'] = cipher().encrypt(json.dumps(tokens).encode()).decode()
    calls = []
    original = FakeAuth.refresh
    def refresh(self, token):
        calls.append(token)
        return original(self, token)
    monkeypatch.setattr(FakeAuth, 'refresh', refresh)
    assert client.get('/api/cart').status_code == 200
    assert client.get('/api/cart').status_code == 200
    assert calls == [old_refresh]
    assert old_refresh not in store.tokens


def test_provider_rejects_session_or_mismatched_identity(client, store, monkeypatch):
    value = login(client)
    monkeypatch.setattr(FakeAuth, 'user', lambda self, token: {'id': str(USER_B)})
    assert client.get('/api/members/me').status_code == 401
    assert digest(value) not in store.sessions


def test_provider_outage_returns_503_and_preserves_session(client, store, monkeypatch):
    value = login(client)
    def down(*args):
        raise HTTPException(status_code=503, detail='provider down')
    monkeypatch.setattr(FakeAuth, 'user', down)
    assert client.get('/api/members/me').status_code == 503
    assert digest(value) in store.sessions


def test_session_creation_failure_does_not_issue_cookie(client, store):
    store.fail_commit_once = True
    response = client.post('/api/auth/login', json={'email': 'buyer@example.com', 'password': PASSWORD})
    assert response.status_code == 503
    assert 'set-cookie' not in response.headers
    assert store.sessions == {}


def test_changed_encryption_key_invalidates_existing_session(client):
    from pydantic import SecretStr
    login(client)
    client.application.config['settings'].secret_key = SecretStr('new-key-' * 8)
    assert client.get('/api/members/me').status_code == 401


def test_revoked_refresh_token_deletes_app_session(client, store):
    value = login(client)
    row = store.sessions[digest(value)]
    with client.application.app_context():
        tokens = json.loads(cipher().decrypt(row['encrypted_tokens'].encode()))
        store.tokens.pop(tokens['refresh_token'])
        tokens['expires_at'] = time.time() - 1
        row['encrypted_tokens'] = cipher().encrypt(json.dumps(tokens).encode()).decode()
    assert client.get('/api/cart').status_code == 401
    assert digest(value) not in store.sessions


def test_refresh_rotation_is_committed_when_followup_user_lookup_is_unavailable(client, store, monkeypatch):
    value = login(client)
    row = store.sessions[digest(value)]
    with client.application.app_context():
        tokens = json.loads(cipher().decrypt(row['encrypted_tokens'].encode()))
        old_refresh = tokens['refresh_token']
        tokens['expires_at'] = time.time() - 1
        row['encrypted_tokens'] = cipher().encrypt(json.dumps(tokens).encode()).decode()
    original = FakeAuth.user
    def unavailable_for_access(self, token):
        if token == old_refresh:
            return original(self, token)
        raise HTTPException(status_code=503, detail='user lookup unavailable')
    monkeypatch.setattr(FakeAuth, 'user', unavailable_for_access)
    assert client.get('/api/cart').status_code == 503
    with client.application.app_context():
        saved = json.loads(cipher().decrypt(store.sessions[digest(value)]['encrypted_tokens'].encode()))
    assert saved['refresh_token'] != old_refresh
    assert saved['refresh_token'] in store.tokens


def test_role_cannot_be_set_through_signup_or_profile(buyer, store):
    body = {'email': 'hacker@example.com', 'password': PASSWORD, 'name': 'hacker', 'role': 'admin'}
    assert buyer.post('/api/auth/signup', json=body).status_code == 422
    assert buyer.patch('/api/members/me', json={'role': 'admin'}).status_code == 422
    assert store.tables['users'][USER_A]['role'] == 'customer'


@pytest.mark.parametrize('path,method', [('/api/admin/products', 'post'),
    (f'/api/admin/products/{P1}', 'put'), ('/api/admin/orders', 'get')])
def test_admin_routes_reject_guest_and_customer(client, settings, path, method):
    assert getattr(client, method)(path).status_code == 401
    authorize(client, settings)
    assert getattr(client, method)(path).status_code == 403


def test_admin_products_orders_and_immediate_role_revocation(buyer, store, monkeypatch):
    store.tables['users'][USER_A]['role'] = 'admin'
    def execute(self, sql, params=()):
        if sql.startswith('INSERT INTO public.products'):
            name, description, price, stock = params
            uid = uuid4()
            row = dict(id=uid, name=name, description=description, price=price, stock=stock)
            store.tables['products'][uid] = row
            return SimpleNamespace(fetchone=lambda: row)
        if sql.startswith('UPDATE public.products'):
            name, description, price, stock, uid = params
            row = store.tables['products'].get(uid)
            if row:
                row.update(name=name, description=description, price=price, stock=stock)
            return SimpleNamespace(fetchone=lambda: row)
        if sql.startswith('SELECT * FROM public.orders'):
            return SimpleNamespace(fetchall=lambda: [])
        raise AssertionError(sql)
    monkeypatch.setattr(MemoryConnection, 'execute', execute)
    payload = {'name': '관리자 상품', 'description': '', 'price': 12300, 'stock': 7}
    created = buyer.post('/api/admin/products', json=payload)
    assert created.status_code == 201
    uid = created.json()['id']
    assert buyer.put('/api/admin/products/' + uid, json={**payload, 'stock': 0}).json()['stock'] == 0
    assert buyer.put('/api/admin/products/' + str(uuid4()), json=payload).status_code == 404
    assert buyer.post('/api/admin/products', json={**payload, 'price': -1}).status_code == 422
    assert buyer.get('/api/admin/orders').status_code == 200
    assert buyer.get('/api/admin/orders?limit=101').status_code == 422
    store.tables['users'][USER_A]['role'] = 'customer'
    assert buyer.get('/api/admin/orders').status_code == 403


def test_password_change_revokes_all_app_sessions(client, store, settings):
    first = login(client)
    second = authorize(client, settings).get_cookie(AUTH_COOKIE_NAME).value
    changed = client.put('/api/members/me/password', json={
        'current_password': PASSWORD, 'new_password': 'Updated-password-2026!',
    })
    assert changed.status_code == 204
    assert digest(first) not in store.sessions and digest(second) not in store.sessions
    client.set_cookie(AUTH_COOKIE_NAME, first)
    assert client.get('/api/members/me').status_code == 401


def test_rest_client_uses_apikey_bearer_and_expected_paths(settings, monkeypatch):
    from app.core import supabase_auth
    calls = []
    class Reply:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self): return b'{"id":"verified-user"}'
    def transport(req, timeout):
        calls.append(req)
        assert timeout == 10
        return Reply()
    monkeypatch.setattr(supabase_auth, 'urlopen', transport)
    auth = SupabaseAuth(settings)
    auth.login('buyer@example.com', PASSWORD)
    auth.refresh('refresh-secret')
    assert auth.user('access-secret')['id'] == 'verified-user'
    auth.logout('access-secret')
    auth.password('access-secret', 'new-password')
    assert [r.full_url.split('/auth/v1')[1] for r in calls] == [
        '/token?grant_type=password', '/token?grant_type=refresh_token', '/user', '/logout?scope=local', '/user']
    assert calls[2].get_header('Authorization') == 'Bearer access-secret'
    assert calls[2].get_header('Apikey') == 'test-anon-key'


@pytest.mark.parametrize('status,expected', [(400, 400), (401, 401), (403, 401), (429, 429), (500, 503)])
def test_provider_errors_do_not_leak_credentials(settings, monkeypatch, status, expected):
    from app.core import supabase_auth
    def fail(*args, **kwargs):
        raise HTTPError('https://auth.invalid', status, 'SECRET_PROVIDER_BODY', {}, None)
    monkeypatch.setattr(supabase_auth, 'urlopen', fail)
    with pytest.raises(HTTPException) as result:
        SupabaseAuth(settings).user('SECRET_TOKEN')
    assert result.value.status_code == expected
    assert 'SECRET' not in result.value.detail
