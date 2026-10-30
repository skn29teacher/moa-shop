import base64
import hashlib
import json
import secrets
import time
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app, g, request

from app.core.errors import HTTPException
from app.core.security import AUTH_COOKIE_NAME, authentication_error
from app.core.supabase_auth import provider
from app.db import sessions, users
from app.db.connection import get_connection


def cipher():
    secret = current_app.config['settings'].secret_key.get_secret_value().encode()
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret).digest()))


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def encrypt(tokens):
    # Store only what is needed to refresh; never store the provider's user metadata.
    data = {k: tokens[k] for k in ('access_token', 'refresh_token', 'expires_in')}
    data['expires_at'] = time.time() + int(data['expires_in'])
    return cipher().encrypt(json.dumps(data).encode()).decode()


def start(connection, user, tokens):
    value = secrets.token_urlsafe(32)
    with connection.transaction():
        sessions.purge_expired(connection)
        sessions.insert(connection, digest(value), user['id'], encrypt(tokens),
                        current_app.config['settings'].session_days)
    return value


def load_session(connection, key):
    row = sessions.lock(connection, key)
    if not row:
        raise authentication_error()
    try:
        tokens = json.loads(cipher().decrypt(row['encrypted_tokens'].encode()))
    except (InvalidToken, ValueError, KeyError):
        raise authentication_error() from None
    return row, tokens


def current():
    if 'auth_user' in g:
        return g.auth_user
    value = request.cookies.get(AUTH_COOKIE_NAME)
    if not value or len(value) > 256:
        raise authentication_error()
    connection = get_connection()
    key = digest(value)
    row, tokens = load_session(connection, key)
    # Normal Supabase /user verification happens without holding SQLite's writer lock.
    # Only refresh rotation requires a serialized read/refresh/update transaction.
    invalid = False
    if tokens['expires_at'] <= time.time() + 30:
        with connection.transaction():
            row, tokens = load_session(connection, key)
            if tokens['expires_at'] <= time.time() + 30:
                try:
                    tokens = provider().refresh(tokens['refresh_token'])
                    sessions.update(connection, key, encrypt(tokens))
                except HTTPException as exc:
                    if exc.status_code not in (400, 401, 403):
                        raise
                    sessions.delete(connection, key)
                    invalid = True
        if invalid:
            raise authentication_error()
    try:
        identity = provider().user(tokens['access_token'])
    except HTTPException as exc:
        if exc.status_code not in (400, 401, 403):
            raise
        with connection.transaction():
            sessions.delete(connection, key)
        raise authentication_error() from None
    # Recheck after the network call: a concurrent logout/password change must take effect.
    row = sessions.lock(connection, key)
    user = users.find_user_by_id(connection, row['user_id']) if row else None
    if (not user or user['deleted_at'] is not None or not user.get('auth_user_id')
            or UUID(identity['id']) != user['auth_user_id']):
        with connection.transaction():
            sessions.delete(connection, key)
        raise authentication_error()
    g.auth_user = user
    return user


def end(connection):
    value = request.cookies.get(AUTH_COOKIE_NAME)
    if not value:
        return
    # Commit local revocation before any network request, even if Supabase is down.
    with connection.transaction():
        row = sessions.lock(connection, digest(value))
        sessions.delete(connection, digest(value))
    if row:
        try:
            tokens = json.loads(cipher().decrypt(row['encrypted_tokens'].encode()))
            provider().logout(tokens['access_token'])
        except (HTTPException, InvalidToken, ValueError, KeyError):
            pass
