"""Only hashes of browser secrets and encrypted provider tokens are persisted."""
import time


def insert(connection, digest, user_id, tokens, days):
    connection.execute("""INSERT INTO auth_sessions
        (token_hash, user_id, encrypted_tokens, expires_at) VALUES (?, ?, ?, ?)""",
        (digest, user_id, tokens, int(time.time()) + days * 86400))


def lock(connection, digest):
    # Refresh callers hold BEGIN IMMEDIATE; ordinary lookups need no write transaction.
    return connection.execute("""SELECT user_id, encrypted_tokens FROM auth_sessions
        WHERE token_hash = ? AND expires_at > ?""", (digest, int(time.time()))).fetchone()


def update(connection, digest, tokens):
    connection.execute('UPDATE auth_sessions SET encrypted_tokens = ? WHERE token_hash = ?', (tokens, digest))


def delete(connection, digest):
    connection.execute('DELETE FROM auth_sessions WHERE token_hash = ?', (digest,))


def delete_user(connection, user_id):
    connection.execute('DELETE FROM auth_sessions WHERE user_id = ?', (user_id,))


def purge_expired(connection):
    connection.execute('DELETE FROM auth_sessions WHERE expires_at <= ?', (int(time.time()),))
