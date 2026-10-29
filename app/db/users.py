from uuid import UUID

from psycopg import Connection


def find_user_by_email(connection: Connection, email: str) -> dict | None:
    return connection.execute(
        """
        SELECT id, email, password_hash, name, phone, address, deleted_at, created_at
        FROM public.users
        WHERE email = %s
        """,
        (email,),
    ).fetchone()


def find_user_by_id(connection: Connection, user_id: UUID) -> dict | None:
    return connection.execute(
        """
        SELECT id, email, name, phone, address, deleted_at, created_at
        FROM public.users
        WHERE id = %s
        """,
        (user_id,),
    ).fetchone()


def insert_user(
    connection: Connection,
    *,
    email: str,
    password_hash: str,
    name: str,
    phone: str | None,
    address: str | None,
) -> dict:
    # 입력값은 항상 바인딩하며 SQL 문자열에 이어 붙이지 않습니다.
    return connection.execute(
        """
        INSERT INTO public.users (email, password_hash, name, phone, address)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id, email, name, phone, address, created_at
        """,
        (email, password_hash, name, phone, address),
    ).fetchone()


def update_profile(
    connection: Connection,
    user_id: UUID,
    *,
    name: str,
    phone: str | None,
    address: str | None,
) -> dict | None:
    return connection.execute(
        """
        UPDATE public.users
        SET name = %s, phone = %s, address = %s, updated_at = now()
        WHERE id = %s AND deleted_at IS NULL
        RETURNING id, email, name, phone, address, created_at
        """,
        (name, phone, address, user_id),
    ).fetchone()


def find_password_hash_for_update(connection: Connection, user_id: UUID) -> dict | None:
    return connection.execute(
        "SELECT password_hash, deleted_at FROM public.users WHERE id = %s FOR UPDATE",
        (user_id,),
    ).fetchone()


def update_password_hash(connection: Connection, user_id: UUID, password_hash: str) -> bool:
    cursor = connection.execute(
        """
        UPDATE public.users SET password_hash = %s, updated_at = now()
        WHERE id = %s AND deleted_at IS NULL
        """,
        (password_hash, user_id),
    )
    return cursor.rowcount == 1


def soft_delete_user(connection: Connection, user_id: UUID) -> bool:
    cursor = connection.execute(
        """
        UPDATE public.users SET deleted_at = now(), updated_at = now()
        WHERE id = %s AND deleted_at IS NULL
        """,
        (user_id,),
    )
    return cursor.rowcount == 1
