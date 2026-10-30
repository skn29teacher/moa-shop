from uuid import UUID

from psycopg import Connection

from app.core.errors import HTTPException
from app.core.security import authentication_error
from app.db import commerce, sessions, users
from app.core.supabase_auth import provider
from app.schemas.members import PasswordChangeRequest, ProfileUpdateRequest
from app.services.commerce_common import lock_active_member, order_snapshot


def get_profile(user: dict) -> dict:
    return user


def update_profile(
    connection: Connection, user_id: UUID, payload: ProfileUpdateRequest
) -> dict:
    with connection.transaction():
        lock_active_member(connection, user_id)
        current = users.find_user_by_id(connection, user_id)
        if current is None or current["deleted_at"] is not None:
            raise authentication_error()
        changes = payload.model_dump(exclude_unset=True)
        result = users.update_profile(
            connection,
            user_id,
            name=changes.get("name", current["name"]),
            phone=changes.get("phone", current["phone"]),
            address=changes.get("address", current["address"]),
        )
        if result is None:
            raise authentication_error()
        return result


def change_password(connection, user_id, payload) -> None:
    user = users.find_user_by_id(connection, user_id)
    # Verify current password with Supabase, never with the legacy users hash.
    try:
        verified = provider().login(user['email'], payload.current_password.get_secret_value())
    except HTTPException as exc:
        if exc.status_code == 401:
            raise HTTPException(status_code=400, detail="현재 비밀번호가 올바르지 않습니다.") from None
        raise
    try:
        if UUID(verified['user']['id']) != user['auth_user_id']:
            raise authentication_error()
        provider().password(verified['access_token'], payload.new_password.get_secret_value())
        with connection.transaction():
            sessions.delete_user(connection, user_id)
    finally:
        try:
            provider().logout(verified['access_token'])
        except HTTPException:
            pass


def delete_member(connection: Connection, user_id: UUID) -> None:
    with connection.transaction():
        lock_active_member(connection, user_id)
        sessions.delete_user(connection, user_id)
        if not users.soft_delete_user(connection, user_id):
            raise authentication_error()


def list_purchase_history(connection: Connection, user_id: UUID) -> list[dict]:
    with connection.transaction():
        lock_active_member(connection, user_id)
        orders = commerce.list_user_orders(connection, user_id)
        return [order_snapshot(connection, order) for order in orders]
