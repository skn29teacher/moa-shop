"""Supabase boundary substitute for offline tests. Production never uses this code."""
from uuid import UUID, uuid4

from app.core.errors import HTTPException
from tests.legacy_security import hash_password, verify_password
from tests.support import utcnow


class FakeAuth:
    def __init__(self, store):
        self.store = store

    def issue(self, user_id):
        access = f'{user_id}:{uuid4()}'
        refresh = f'{user_id}:{uuid4()}'
        self.store.tokens[access] = user_id
        self.store.tokens[refresh] = user_id
        return dict(access_token=access, refresh_token=refresh, expires_in=3600,
                    user={'id': str(user_id)})

    def signup(self, payload):
        email = str(payload.email)
        if any(u['email'] == email for u in self.store.tables['users'].values()):
            return {}  # Supabase can mask existing accounts; response must remain generic.
        uid = uuid4()
        self.store.tables['users'][uid] = dict(
            id=uid, auth_user_id=uid, role='customer', email=email,
            password_hash=hash_password(payload.password.get_secret_value()),
            name=payload.name, phone=payload.phone, address=payload.address,
            created_at=utcnow(), deleted_at=None,
        )
        return {'id': str(uid)}

    def login(self, email, password):
        user = next((u for u in self.store.tables['users'].values() if u['email'] == email), None)
        if not user or not verify_password(password, user['password_hash']):
            raise HTTPException(status_code=401, detail='이메일 또는 비밀번호가 올바르지 않거나 이메일 인증이 필요합니다.')
        return self.issue(user['auth_user_id'])

    def user(self, token):
        if token not in self.store.tokens:
            raise HTTPException(status_code=401, detail='invalid token')
        return {'id': str(self.store.tokens[token])}

    def refresh(self, token):
        user = self.user(token)
        del self.store.tokens[token]
        return self.issue(UUID(user['id']))

    def logout(self, token):
        self.store.tokens.pop(token, None)

    def password(self, token, password):
        uid = UUID(self.user(token)['id'])
        self.store.tables['users'][uid]['password_hash'] = hash_password(password)


def install_sessions(monkeypatch, store):
    from app.db import sessions
    store.tables["sessions"] = {}
    store.tokens = {}

    def insert(connection, digest, user_id, tokens, days):
        store.sessions[digest] = dict(user_id=user_id, encrypted_tokens=tokens)

    def update(connection, digest, tokens):
        store.sessions[digest]['encrypted_tokens'] = tokens

    def delete_user(connection, user_id):
        for key in list(store.sessions):
            if store.sessions[key]['user_id'] == user_id:
                del store.sessions[key]

    monkeypatch.setattr(sessions, 'insert', insert)
    monkeypatch.setattr(sessions, 'lock', lambda c, k: store.sessions.get(k))
    monkeypatch.setattr(sessions, 'update', update)
    monkeypatch.setattr(sessions, 'delete', lambda c, k: store.sessions.pop(k, None))
    monkeypatch.setattr(sessions, 'delete_user', delete_user)
    monkeypatch.setattr(sessions, 'purge_expired', lambda c: None)
