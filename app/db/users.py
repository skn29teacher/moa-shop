from uuid import UUID

from app.db.connection import Connection
from app.core.errors import HTTPException
from app.schemas.members import ProfileUpdateRequest
from pydantic import ValidationError


def find_user_by_id(connection: Connection, user_id: UUID) -> dict | None:
    return connection.execute(
        """
        SELECT id, auth_user_id, role, email, name, phone, address, deleted_at, created_at
        FROM users
        WHERE id = ?
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
        UPDATE users
        SET name = ?, phone = ?, address = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
        WHERE id = ? AND deleted_at IS NULL
        RETURNING id, auth_user_id, role, email, name, phone, address, created_at
        """,
        (name, phone, address, user_id),
    ).fetchone()


def soft_delete_user(connection: Connection, user_id: UUID) -> bool:
    cursor = connection.execute(
        """
        UPDATE users SET deleted_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
        WHERE id = ? AND deleted_at IS NULL
        """,
        (user_id,),
    )
    return cursor.rowcount == 1


def find_user_by_auth_id(connection: Connection, auth_id: UUID) -> dict | None:
    return connection.execute(
        "SELECT id, auth_user_id, role, email, name, phone, address, deleted_at, created_at "
        "FROM users WHERE auth_user_id = ?", (auth_id,),
    ).fetchone()


def ensure_auth_profile(connection: Connection, identity: dict) -> dict:
    """Create only after successful Auth login. Identity is from Supabase, never browser JSON."""
    auth_id = UUID(identity['id'])
    with connection.transaction():
        existing = find_user_by_auth_id(connection, auth_id)
        if existing:
            return existing  # Preserve role, local profile edits, and soft deletion.
        email = str(identity.get('email') or '').strip().lower()
        if not email:
            raise HTTPException(status_code=401, detail='이메일이 있는 Supabase 계정이 필요합니다.')
        collision = connection.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
        if collision:
            raise HTTPException(status_code=409, detail='기존 회원 계정 연결을 관리자에게 요청하세요.')
        metadata = identity.get('user_metadata') or {}
        if not isinstance(metadata, dict):
            metadata = {}
        def text(key, limit):
            value = metadata.get(key)
            return value.strip()[:limit] or None if isinstance(value, str) else None
        fields = dict(name=text('name', 100) or '회원', phone=text('phone', 30), address=text('address', 500))
        try:
            fields = ProfileUpdateRequest(**fields).model_dump()
        except ValidationError:
            fields['phone'] = None  # Invalid user-editable metadata must not break login.
        # Role always defaults to customer. Do not copy metadata.role or app_metadata.role.
        return connection.execute('''INSERT INTO users (id, auth_user_id, email, name, phone, address)
            VALUES (?, ?, ?, ?, ?, ?) RETURNING *''',
            (auth_id, auth_id, email, fields['name'], fields['phone'], fields['address'])).fetchone()
