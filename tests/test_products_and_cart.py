import pytest

from tests.support import MISSING, P1, P2, SOLD_OUT, USER_A, add, assert_error, checkout, snapshot


def test_products_are_public_and_paginated(client):
    first = client.get("/api/products?limit=2&offset=0")
    assert first.status_code == 200
    body = first.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert body["limit"] == 2 and body["offset"] == 0
    assert client.get("/api/products?limit=0").status_code == 422
    assert client.get("/api/products?limit=101").status_code == 422
    assert client.get("/api/products?offset=-1").status_code == 422


def test_product_detail_includes_sold_out_item_and_missing_is_404(client):
    response = client.get(f"/api/products/{SOLD_OUT}")
    assert response.status_code == 200
    assert response.json()["stock"] == 0
    assert_error(client.get(f"/api/products/{MISSING}"), 404)
    assert client.get("/api/products/not-a-uuid").status_code == 422


@pytest.mark.parametrize("method,path,body", [
    ("get", "/api/cart", None),
    ("post", "/api/cart/items", {"product_id": str(P1), "quantity": 1}),
    ("patch", f"/api/cart/items/{P1}", {"quantity": 1}),
    ("delete", f"/api/cart/items/{P1}", None),
    ("post", "/api/orders", {"source": "cart", "recipient_name": "Buyer",
                               "recipient_phone": "010-1234-5678", "shipping_address": "Seoul"}),
    ("post", f"/api/orders/{P1}/payments", {"simulate_success": True}),
])
def test_protected_endpoints_require_login(client, method, path, body):
    response = getattr(client, method)(path, json=body) if body is not None else getattr(client, method)(path)
    assert_error(response, 401)


def test_empty_cart_read_does_not_create_order(buyer, store):
    response = buyer.get("/api/cart")
    assert response.status_code == 200
    assert response.json()["id"] is None
    assert response.json()["items"] == []
    assert response.json()["total_amount"] == 0
    assert store.tables["orders"] == {}


def test_add_and_repeat_add_store_product_and_logged_in_user(buyer, store):
    first = add(buyer, P1, 2)
    assert first.status_code == 200, first.text
    cart = first.json()
    assert cart["user_id"] == str(USER_A)
    assert cart["status"] == "cart"
    assert cart["total_amount"] == 38_000
    assert len(cart["items"]) == 1
    assert cart["items"][0]["product_id"] == str(P1)
    assert cart["items"][0]["product_name"] == "티셔츠"
    assert cart["items"][0]["quantity"] == 2
    assert cart["items"][0]["unit_price"] == 19_000
    assert store.tables["products"][P1]["stock"] == 10

    second = add(buyer, P1, 3)
    assert second.status_code == 200
    assert len(second.json()["items"]) == 1
    assert second.json()["items"][0]["quantity"] == 5
    assert second.json()["total_amount"] == 95_000


def test_add_another_product_and_update_quantity_sets_absolute_value(buyer):
    assert add(buyer, P1, 1).status_code == 200
    response = add(buyer, P2, 2)
    assert response.status_code == 200
    assert len(response.json()["items"]) == 2
    changed = buyer.patch(f"/api/cart/items/{P1}", json={"quantity": 4})
    assert changed.status_code == 200
    rows = {item["product_id"]: item for item in changed.json()["items"]}
    assert rows[str(P1)]["quantity"] == 4
    assert rows[str(P2)]["quantity"] == 2
    assert changed.json()["total_amount"] == 106_000


def test_cart_delete_recalculates_total_and_missing_item_returns_404(buyer):
    add(buyer, P1, 1)
    add(buyer, P2, 1)
    response = buyer.delete(f"/api/cart/items/{P1}")
    assert response.status_code == 200
    assert [item["product_id"] for item in response.json()["items"]] == [str(P2)]
    assert response.json()["total_amount"] == 15_000
    assert_error(buyer.delete(f"/api/cart/items/{P1}"), 404)
    assert_error(buyer.delete(f"/api/cart/items/{MISSING}"), 404)


@pytest.mark.parametrize("body", [
    {"product_id": str(P1), "quantity": 0},
    {"product_id": str(P1), "quantity": -1},
    {"product_id": str(P1), "quantity": 2_147_483_648},
    {"product_id": str(P1), "quantity": True},
    {"product_id": "not-a-uuid", "quantity": 1},
    {"product_id": str(P1), "quantity": 1, "extra": "x"},
])
def test_cart_add_rejects_invalid_payload_without_writes(buyer, store, body):
    before = snapshot(store)
    response = buyer.post("/api/cart/items", json=body)
    assert response.status_code == 422
    assert snapshot(store) == before


def test_cart_rejects_missing_or_insufficient_stock_and_rolls_back(buyer, store):
    before = snapshot(store)
    assert_error(add(buyer, MISSING, 1), 404)
    assert snapshot(store) == before
    assert_error(add(buyer, SOLD_OUT, 1), 409)
    assert snapshot(store) == before
    assert_error(add(buyer, P1, 11), 409)
    assert snapshot(store) == before
    add(buyer, P1, 4)
    current = snapshot(store)
    assert_error(add(buyer, P1, 7), 409)
    assert snapshot(store) == current
    assert_error(buyer.patch(f"/api/cart/items/{P1}", json={"quantity": 11}), 409)
    assert snapshot(store) == current


def test_change_quantity_requires_existing_cart_and_item(buyer):
    assert_error(buyer.patch(f"/api/cart/items/{P1}", json={"quantity": 1}), 404)
    add(buyer, P1, 1)
    assert_error(buyer.patch(f"/api/cart/items/{P2}", json={"quantity": 1}), 404)


def test_cart_belongs_to_each_authenticated_member(client, settings, buyer):
    add(buyer, P1, 1)
    from tests.support import USER_B, authorize
    other = authorize(client, settings, USER_B)
    assert other.get("/api/cart").json()["items"] == []
    assert add(other, P2, 1).status_code == 200
    assert len(other.get("/api/cart").json()["items"]) == 1
    authorize(buyer, settings, USER_A)
    assert len(buyer.get("/api/cart").json()["items"]) == 1


def test_cart_checkout_keeps_cart_rows_as_pending_order(buyer, store):
    add(buyer, P1, 2)
    stock_before = store.tables["products"][P1]["stock"]
    response = checkout(buyer)
    assert response.status_code == 201, response.text
    order = response.json()
    assert order["status"] == "pending"
    assert order["total_amount"] == 38_000
    assert order["items"][0]["product_id"] == str(P1)
    assert order["items"][0]["unit_price"] == 19_000
    assert store.tables["orders"][__import__("uuid").UUID(order["id"])]["status"] == "pending"
    assert store.tables["products"][P1]["stock"] == stock_before
