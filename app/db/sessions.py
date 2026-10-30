"""Only hashes of browser secrets and encrypted provider tokens are persisted."""


def insert(connection, digest, user_id, tokens, days):
    connection.execute('''INSERT INTO public.auth_sessions
        (token_hash, user_id, encrypted_tokens, expires_at)
        VALUES (%s, %s, %s, now() + %s * interval '1 day')''',
        (digest, user_id, tokens, days))


def lock(connection, digest):
    return connection.execute('''SELECT user_id, encrypted_tokens FROM public.auth_sessions
        WHERE token_hash = %s AND expires_at > now() FOR UPDATE''', (digest,)).fetchone()


def update(connection, digest, tokens):
    connection.execute('UPDATE public.auth_sessions SET encrypted_tokens = %s WHERE token_hash = %s',
                       (tokens, digest))


def delete(connection, digest):
    connection.execute('DELETE FROM public.auth_sessions WHERE token_hash = %s', (digest,))


def delete_user(connection, user_id):
    connection.execute('DELETE FROM public.auth_sessions WHERE user_id = %s', (user_id,))


def purge_expired(connection):
    connection.execute('DELETE FROM public.auth_sessions WHERE expires_at <= now()')
