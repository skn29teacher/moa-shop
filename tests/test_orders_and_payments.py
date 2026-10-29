from uuid import UUID

import pytest

from tests.support import (
    MISSING, P1, P2, SOLD_OUT, USER_B, SHIPPING, add, assert_error, buy_now,
    checkout, pay, snapshot,
)


def test_order_rejects_empty_cart_and_bad_shipping(buyer, store):
    before = snapshot(store)
    empty = checkout(buyer)
    assert_error(empty, 409)
    assert snapshot(store) == before
    add(buyer, P1, 1)
    for field, value in [("recipient_name", " "), ("recipient_phone", "123"),
                         ("shipping_address", " ")]:
        body = {"source": "cart", **SHIPPING, field: value}
        assert buyer.post("/api/orders", json=body).status_code == 422
    assert buyer.post("/api/orders", json={"source": "cart", **SHIPPING, "unknown": 1}).status_code == 422


def test_buy_now_creates_order_item_and_preserves_cart(buyer, store):
    add(buyer, P2, 2)
    cart_before = buyer.get("/api/cart").json()
    stock_before = store.tables["products"][P1]["stock"]
    response = buy_now(buyer, P1, 3)
    assert response.status_code == 201, response.text
    order = response.json()
    assert order["status"] == "pending"
    assert order["total_amount"] == 57_000
    assert [(row["product_id"], row["product_name"], row["quantity"], row["unit_price"])
            for row in order["items"]] == [(str(P1), "티셔츠", 3, 19_000)]
    assert buyer.get("/api/cart").json() == cart_before
    assert store.tables["products"][P1]["stock"] == stock_before


@pytest.mark.parametrize("payload", [
    {"source": "buy_now", "product_id": str(P1), "quantity": 0, **SHIPPING},
    {"source": "buy_now", "product_id": str(P1), "quantity": True, **SHIPPING},
    {"source": "buy_now", "product_id": "bad-id", "quantity": 1, **SHIPPING},
    {"source": "unknown", "product_id": str(P1), "quantity": 1, **SHIPPING},
    {"source": "buy_now", "product_id": str(P1), "quantity": 1, **SHIPPING, "unexpected": 1},
])
def test_order_creation_rejects_invalid_payload_without_writes(buyer, store, payload):
    before = snapshot(store)
    assert buyer.post("/api/orders", json=payload).status_code == 422
    assert snapshot(store) == before


def test_buy_now_rejects_missing_or_insufficient_inventory(buyer, store):
    before = snapshot(store)
    assert_error(buy_now(buyer, MISSING, 1), 404)
    assert snapshot(store) == before
    assert_error(buy_now(buyer, SOLD_OUT, 1), 409)
    assert snapshot(store) == before
    assert_error(buy_now(buyer, P1, 11), 409)
    assert snapshot(store) == before


def test_order_total_overflow_is_rejected_without_creating_order(buyer, store):
    store.tables["products"][P1]["price"] = 999_999_999_999
    store.tables["products"][P1]["stock"] = 200
    before = snapshot(store)
    response = buy_now(buyer, P1, 200)
    assert_error(response, 422)
    assert snapshot(store) == before


def test_checkout_revalidates_stock_and_keeps_cart_when_stock_changed(buyer, store):
    add(buyer, P1, 2)
    store.tables["products"][P1]["stock"] = 1
    before = snapshot(store)
    assert_error(checkout(buyer), 409)
    assert snapshot(store) == before
    assert store.tables["orders"][next(iter(store.tables["orders"]))]["status"] == "cart"


def test_checkout_snapshots_current_product_price(buyer, store):
    add(buyer, P1, 2)
    store.tables["products"][P1]["price"] = 21_000
    order = checkout(buyer)
    assert order.status_code == 201, order.text
    assert order.json()["total_amount"] == 42_000
    assert order.json()["items"][0]["unit_price"] == 21_000


def test_order_detail_only_exposes_owned_non_cart_orders(client, settings, buyer):
    order = buy_now(buyer, P1, 1).json()
    assert client.get(f"/api/orders/{order['id']}").status_code == 200
    from tests.support import authorize
    other = authorize(client, settings, USER_B)
    assert_error(other.get(f"/api/orders/{order['id']}"), 404)
    assert_error(buyer.get(f"/api/orders/{MISSING}"), 404)
    assert buyer.get("/api/orders/not-a-uuid").status_code == 422
    add(buyer, P2, 1)
    cart_id = buyer.get("/api/cart").json()["id"]
    assert_error(buyer.get(f"/api/orders/{cart_id}"), 404)


def test_payment_failure_is_saved_then_retry_can_succeed_and_repeat_is_idempotent(buyer, store):
    order = buy_now(buyer, P1, 2).json()
    first = pay(buyer, order["id"], success=False)
    assert first.status_code == 200, first.text
    failed = first.json()
    assert failed["payment"]["status"] == "failed"
    assert failed["payment"]["amount"] == 38_000
    assert failed["order_status"] == "pending"
    assert failed["already_paid"] is False
    assert store.tables["products"][P1]["stock"] == 10

    second = pay(buyer, order["id"], success=True)
    assert second.status_code == 200, second.text
    paid = second.json()
    assert paid["payment"]["status"] == "success"
    assert paid["order_status"] == "paid"
    assert paid["already_paid"] is False
    assert store.tables["products"][P1]["stock"] == 8
    assert len(store.tables["payments"]) == 2

    repeated = pay(buyer, order["id"], success=True)
    assert repeated.status_code == 200
    assert repeated.json()["already_paid"] is True
    assert repeated.json()["payment"]["id"] == paid["payment"]["id"]
    assert len(store.tables["payments"]) == 2
    assert store.tables["products"][P1]["stock"] == 8


def test_payment_inventory_shortage_records_failure_and_does_not_charge(buyer, store):
    order = buy_now(buyer, P1, 4).json()
    store.tables["products"][P1]["stock"] = 3
    before_stock = store.tables["products"][P1]["stock"]
    response = pay(buyer, order["id"], success=True)
    assert response.status_code == 409, response.text
    result = response.json()
    assert result["payment"]["status"] == "failed"
    assert "재고 부족" in result["payment"]["failure_reason"]
    assert result["order_status"] == "pending"
    assert store.tables["products"][P1]["stock"] == before_stock
    assert store.tables["orders"][UUID(order["id"])]["status"] == "pending"
    assert len(store.tables["payments"]) == 1


def test_payment_rejects_cart_foreign_or_missing_order(buyer, client, settings):
    add(buyer, P1, 1)
    cart_id = buyer.get("/api/cart").json()["id"]
    cart_payment = pay(buyer, cart_id)
    assert_error(cart_payment, 409)
    assert "주문 상태" in cart_payment.json()["detail"]
    order = buy_now(buyer, P1, 1).json()
    from tests.support import authorize
    other = authorize(client, settings, USER_B)
    assert_error(pay(other, order["id"]), 404)
    assert_error(pay(buyer, MISSING), 404)


@pytest.mark.parametrize("body", [
    {"simulate_success": "true"},
    {"simulate_success": 1},
    {"simulate_success": None},
    {"simulate_success": True, "amount": 1},
])
def test_payment_rejects_invalid_request_body_without_writes(buyer, store, body):
    order = buy_now(buyer, P1, 1).json()
    before = snapshot(store)
    response = buyer.post(f"/api/orders/{order['id']}/payments", json=body)
    assert response.status_code == 422
    assert snapshot(store) == before


def test_payment_detects_order_amount_corruption(buyer, store):
    order = buy_now(buyer, P1, 1).json()
    store.tables["orders"][UUID(order["id"])]["total_amount"] += 1
    before_stock = store.tables["products"][P1]["stock"]
    response = pay(buyer, order["id"])
    assert_error(response, 409)
    assert store.tables["products"][P1]["stock"] == before_stock
    assert store.tables["payments"] == {}


def test_payment_rolls_back_stock_if_late_stock_update_fails(buyer, store, monkeypatch):
    order = buy_now(buyer, P1, 2).json()
    before = snapshot(store)
    from app.services import payments
    real_decrease = payments.decrease_stock

    def mutate_then_report_failure(connection, product_id, quantity):
        real_decrease(connection, product_id, quantity)
        return False

    monkeypatch.setattr(payments, "decrease_stock", mutate_then_report_failure)
    response = pay(buyer, order["id"], success=True)
    assert_error(response, 409)
    assert snapshot(store) == before


def test_database_failure_during_payment_returns_service_unavailable_and_rolls_back(buyer, store, monkeypatch):
    from psycopg import OperationalError
    from app.db import commerce

    order = buy_now(buyer, P1, 2).json()
    before = snapshot(store)

    def fail_payment_insert(*args, **kwargs):
        raise OperationalError("simulated database failure")

    monkeypatch.setattr(commerce, "insert_payment", fail_payment_insert)
    response = pay(buyer, order["id"], success=True)
    assert response.status_code == 503
    assert "simulated database failure" not in response.text
    assert snapshot(store) == before
