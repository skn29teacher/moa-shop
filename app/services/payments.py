from uuid import UUID

from psycopg import Connection

from app.core.errors import HTTPException
from app.db import commerce as db
from app.db.products import decrease_stock, lock_products
from app.services.commerce_common import lock_active_member


def pay_order(
    connection: Connection, user_id: UUID, order_id: UUID, simulate_success: bool
) -> tuple[dict, int]:
    # 회원 → 주문 → 상품(ID 순서)로 잠급니다. 응답 전에 커밋을 완료합니다.
    with connection.transaction():
        lock_active_member(connection, user_id)
        order = db.find_owned_order(connection, order_id, user_id, lock=True)
        if order is None:
            raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")
        existing = db.find_successful_payment(connection, order_id)
        if order["status"] == "paid":
            if existing is None or int(existing["amount"]) != int(order["total_amount"]):
                raise HTTPException(status_code=409, detail="주문과 결제 기록이 일치하지 않습니다.")
            return {"payment": existing, "order_status": "paid", "already_paid": True}, 200
        if order["status"] != "pending" or existing is not None:
            raise HTTPException(status_code=409, detail="결제할 수 있는 주문 상태가 아닙니다.")

        items = db.list_items(connection, order_id)
        amount = int(order["total_amount"])
        if not items or amount <= 0 or sum(int(item["line_amount"]) for item in items) != amount:
            raise HTTPException(status_code=409, detail="주문 금액과 주문상품 정보를 확인하세요.")
        products = lock_products(connection, [item["product_id"] for item in items])
        shortage = next(
            (item for item in items if item["product_id"] not in products
             or products[item["product_id"]]["stock"] < item["quantity"]),
            None,
        )
        if shortage:
            reason = f"재고 부족 (상품 ID: {shortage['product_id']})"
            payment = db.insert_payment(connection, order_id, amount, success=False, reason=reason)
            result = {"payment": payment, "order_status": "pending", "already_paid": False}
            http_status = 409
        elif not simulate_success:
            payment = db.insert_payment(connection, order_id, amount, success=False, reason="모의 결제 실패")
            result = {"payment": payment, "order_status": "pending", "already_paid": False}
            http_status = 200
        else:
            for item in items:
                if not decrease_stock(connection, item["product_id"], item["quantity"]):
                    # 잠금 이후의 예외적 불일치는 성공 기록을 남기지 않고 전부 롤백합니다.
                    raise HTTPException(status_code=409, detail="재고 정보가 변경되어 결제를 완료하지 못했습니다.")
            payment = db.insert_payment(connection, order_id, amount, success=True)
            db.mark_order_paid(connection, order_id)
            result = {"payment": payment, "order_status": "paid", "already_paid": False}
            http_status = 200
    # 재고 부족도 실패 기록을 커밋해야 하므로 트랜잭션 안에서 HTTPException을 던지지 않습니다.
    return result, http_status
