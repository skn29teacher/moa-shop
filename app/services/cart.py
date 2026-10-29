from uuid import UUID

from fastapi import HTTPException
from psycopg import Connection

from app.db import commerce as db
from app.db.products import lock_products
from app.services.commerce_common import cart_snapshot, lock_active_member, require_amount, require_stock


def get_cart(connection: Connection, user_id: UUID) -> dict:
    # 읽기 사이에 다른 요청이 수량을 바꾸지 않도록 짧은 회원·장바구니 잠금을 사용합니다.
    with connection.transaction():
        lock_active_member(connection, user_id)
        return cart_snapshot(connection, user_id, db.find_cart(connection, user_id, lock=True))


def add_item(connection: Connection, user_id: UUID, product_id: UUID, quantity: int) -> dict:
    with connection.transaction():
        lock_active_member(connection, user_id)
        cart = db.find_cart(connection, user_id, lock=True)
        if cart is None:
            cart = db.insert_cart(connection, user_id)
        product = lock_products(connection, [product_id]).get(product_id)
        if product is None:
            raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다.")
        item = next((item for item in db.list_items(connection, cart["id"])
                     if item["product_id"] == product_id), None)
        new_quantity = quantity + (item["quantity"] if item else 0)
        require_stock(product, new_quantity)
        if item:
            # 기존 장바구니 단가를 유지하고 주문 생성 시 현재 단가로 재확정합니다.
            db.update_quantity(connection, item["id"], new_quantity)
        else:
            db.insert_item(connection, cart["id"], product, quantity)
        total = require_amount(db.calculate_total(connection, cart["id"]))
        cart = db.update_cart_total(connection, cart["id"], total)
        return cart_snapshot(connection, user_id, cart)


def change_quantity(connection: Connection, user_id: UUID, product_id: UUID, quantity: int) -> dict:
    with connection.transaction():
        lock_active_member(connection, user_id)
        cart = db.find_cart(connection, user_id, lock=True)
        if cart is None:
            raise HTTPException(status_code=404, detail="장바구니 상품을 찾을 수 없습니다.")
        product = lock_products(connection, [product_id]).get(product_id)
        item = next((item for item in db.list_items(connection, cart["id"])
                     if item["product_id"] == product_id), None)
        if item is None or product is None:
            raise HTTPException(status_code=404, detail="장바구니 상품을 찾을 수 없습니다.")
        require_stock(product, quantity)
        db.update_quantity(connection, item["id"], quantity)
        total = require_amount(db.calculate_total(connection, cart["id"]))
        cart = db.update_cart_total(connection, cart["id"], total)
        return cart_snapshot(connection, user_id, cart)


def remove_item(connection: Connection, user_id: UUID, product_id: UUID) -> dict:
    with connection.transaction():
        lock_active_member(connection, user_id)
        cart = db.find_cart(connection, user_id, lock=True)
        if cart is None:
            raise HTTPException(status_code=404, detail="장바구니 상품을 찾을 수 없습니다.")
        item = next((item for item in db.list_items(connection, cart["id"])
                     if item["product_id"] == product_id), None)
        if item is None:
            raise HTTPException(status_code=404, detail="장바구니 상품을 찾을 수 없습니다.")
        db.delete_item(connection, item["id"])
        cart = db.update_cart_total(connection, cart["id"], db.calculate_total(connection, cart["id"]))
        return cart_snapshot(connection, user_id, cart)
