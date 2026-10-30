from uuid import UUID

from psycopg import Connection


def find_user_by_id(connection: Connection, user_id: UUID) -> dict | None:
    return connection.execute(
        """
        SELECT id, auth_user_id, role, email, name, phone, address, deleted_at, created_at
        FROM public.users
        WHERE id = %s
        """,
        (user_id,),
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
        RETURNING id, auth_user_id, role, email, name, phone, address, created_at
        """,
        (name, phone, address, user_id),
    ).fetchone()


def soft_delete_user(connection: Connection, user_id: UUID) -> bool:
    cursor = connection.execute(
        """
        UPDATE public.users SET deleted_at = now(), updated_at = now()
        WHERE id = %s AND deleted_at IS NULL
        """,
        (user_id,),
    )
    return cursor.rowcount == 1


def find_user_by_auth_id(connection: Connection, auth_id: UUID) -> dict | None:
    return connection.execute(
        "SELECT id, auth_user_id, role, email, name, phone, address, deleted_at, created_at "
        "FROM public.users WHERE auth_user_id = %s", (auth_id,),
    ).fetchone()
