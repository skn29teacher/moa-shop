from uuid import UUID

from fastapi import HTTPException, status
from psycopg import Connection

from app.core.security import authentication_error, hash_password, verify_password
from app.db import commerce, users
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


def change_password(
    connection: Connection, user_id: UUID, payload: PasswordChangeRequest
) -> None:
    with connection.transaction():
        member = users.find_password_hash_for_update(connection, user_id)
        if member is None or member["deleted_at"] is not None:
            raise authentication_error()
        if not verify_password(payload.current_password.get_secret_value(), member["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="현재 비밀번호가 올바르지 않습니다.",
            )
        updated = users.update_password_hash(
            connection, user_id, hash_password(payload.new_password.get_secret_value())
        )
        if not updated:
            raise authentication_error()


def delete_member(connection: Connection, user_id: UUID) -> None:
    with connection.transaction():
        lock_active_member(connection, user_id)
        if not users.soft_delete_user(connection, user_id):
            raise authentication_error()


def list_purchase_history(connection: Connection, user_id: UUID) -> list[dict]:
    with connection.transaction():
        lock_active_member(connection, user_id)
        orders = commerce.list_user_orders(connection, user_id)
        return [order_snapshot(connection, order) for order in orders]
