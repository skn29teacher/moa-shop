from uuid import UUID

from app.db.connection import Connection

from app.core.errors import HTTPException
from app.db import commerce as db
from app.db.products import lock_products
from app.schemas.orders import BuyNowOrderRequest, CartOrderRequest
from app.services.commerce_common import lock_active_member, order_snapshot, require_amount, require_stock


def create_order(
    connection: Connection, user_id: UUID, payload: CartOrderRequest | BuyNowOrderRequest
) -> dict:
    with connection.transaction():
        lock_active_member(connection, user_id)
        shipping = payload.model_dump(include={"recipient_name", "recipient_phone", "shipping_address"})
        if isinstance(payload, BuyNowOrderRequest):
            product = lock_products(connection, [payload.product_id]).get(payload.product_id)
            if product is None:
                raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다.")
            require_stock(product, payload.quantity)
            total = require_amount(int(product["price"]) * payload.quantity)
            # 바로 구매는 기존 cart를 변경하지 않고 별도 pending 주문을 만듭니다.
            order = db.insert_pending_order(connection, user_id, total, shipping)
            db.insert_item(connection, order["id"], product, payload.quantity)
        else:
            cart = db.find_cart(connection, user_id, lock=True)
            if cart is None:
                raise HTTPException(status_code=409, detail="장바구니가 비어 있습니다.")
            items = db.list_items(connection, cart["id"])
            if not items:
                raise HTTPException(status_code=409, detail="장바구니가 비어 있습니다.")
            products = lock_products(connection, [item["product_id"] for item in items])
            total = 0
            for item in items:
                product = products.get(item["product_id"])
                if product is None:
                    raise HTTPException(status_code=409, detail="주문할 상품 정보를 확인할 수 없습니다.")
                require_stock(product, item["quantity"])
                total += int(product["price"]) * item["quantity"]
            require_amount(total)
            # 검증을 모두 통과한 뒤 상품명·가격·합계를 함께 확정합니다.
            for item in items:
                db.confirm_item_price(connection, item["id"], products[item["product_id"]])
            order = db.checkout_cart(connection, cart["id"], total, shipping)
        return order_snapshot(connection, order)


def get_order(connection: Connection, user_id: UUID, order_id: UUID) -> dict:
    with connection.transaction():
        lock_active_member(connection, user_id)
        order = db.find_owned_order(connection, order_id, user_id, lock=True)
        # 다른 회원의 주문 존재 여부와 장바구니를 주문 상세에서 노출하지 않습니다.
        if order is None or order["status"] == "cart":
            raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")
        return order_snapshot(connection, order)
