from uuid import UUID

from fastapi import HTTPException
from psycopg import Connection

from app.core.security import authentication_error
from app.db import commerce as db


MAX_AMOUNT = 99_999_999_999_999


def lock_active_member(connection: Connection, user_id: UUID) -> None:
    member = db.lock_member(connection, user_id)
    if not member or member["deleted_at"] is not None:
        raise authentication_error()


def require_amount(total: int) -> int:
    if not 0 <= total <= MAX_AMOUNT:
        raise HTTPException(status_code=422, detail="주문 합계가 저장 가능한 금액 범위를 초과합니다.")
    return total


def require_stock(product: dict, quantity: int) -> None:
    if quantity > product["stock"]:
        raise HTTPException(status_code=409, detail="상품 재고가 부족합니다. 수량을 확인하세요.")


def cart_snapshot(connection: Connection, user_id: UUID, cart: dict | None) -> dict:
    if cart is None:
        return {"id": None, "user_id": user_id, "total_amount": 0, "items": []}
    return {**cart, "items": db.list_items(connection, cart["id"])}


def order_snapshot(connection: Connection, order: dict) -> dict:
    return {**order, "items": db.list_items(connection, order["id"])}
