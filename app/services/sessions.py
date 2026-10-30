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


def current():
    if 'auth_user' in g:
        return g.auth_user
    value = request.cookies.get(AUTH_COOKIE_NAME)
    if not value or len(value) > 256:
        raise authentication_error()
    connection = get_connection()
    key = digest(value)
    invalid = False
    failure = None
    with connection.transaction():
        row = sessions.lock(connection, key)
        if not row:
            raise authentication_error()
        try:
            tokens = json.loads(cipher().decrypt(row['encrypted_tokens'].encode()))
        except (InvalidToken, ValueError, KeyError):
            raise authentication_error() from None
        user = users.find_user_by_id(connection, row['user_id'])
        if not user or user['deleted_at'] is not None or not user.get('auth_user_id'):
            invalid = True
        else:
            try:
                # Row lock serializes refresh-token rotation across tabs/workers.
                if tokens['expires_at'] <= time.time() + 30:
                    tokens = provider().refresh(tokens['refresh_token'])
                    sessions.update(connection, key, encrypt(tokens))
                identity = provider().user(tokens['access_token'])
                invalid = UUID(identity['id']) != user['auth_user_id']
            except HTTPException as exc:
                if exc.status_code not in (400, 401, 403):
                    failure = exc
                else:
                    invalid = True
            if not invalid and failure is None:
                g.auth_user = user
        if invalid:
            sessions.delete(connection, key)
    if invalid:
        raise authentication_error()
    if failure:
        raise failure
    return g.auth_user


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
