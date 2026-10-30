from copy import deepcopy
from datetime import datetime, timezone
from uuid import UUID

from flask import Response

from app.core.security import AUTH_COOKIE_NAME


ORIGIN = "http://127.0.0.1:8000"
PASSWORD = "Test-password-2026!"
USER_A = UUID(int=1)
USER_B = UUID(int=2)
P1 = UUID(int=1001)
P2 = UUID(int=1002)
SOLD_OUT = UUID(int=1003)
MISSING = UUID(int=999999)
SHIPPING = {
    "recipient_name": "김테스트",
    "recipient_phone": "010-1234-5678",
    "shipping_address": "서울시 테스트로 10",
}


def utcnow():
    return datetime.now(timezone.utc)


def seed_rows(password_hash):
    now = utcnow()
    users = {}
    for user_id, email in [(USER_A, "buyer@example.com"), (USER_B, "other@example.com")]:
        users[user_id] = dict(
            id=user_id, email=email, password_hash=password_hash, name="김테스트",
            phone=None, address=None, deleted_at=None, created_at=now, updated_at=now,
        )
    products = {}
    for product_id, name, price, stock in [
        (P1, "티셔츠", 19000, 10), (P2, "가방", 15000, 5), (SOLD_OUT, "품절상품", 5000, 0)
    ]:
        products[product_id] = dict(
            id=product_id, name=name, description="테스트 상품", price=price,
            stock=stock, created_at=now, updated_at=now,
        )
    return dict(users=users, products=products, orders={}, items={}, payments={})


class FlaskTestResponse(Response):
    def json(self):
        return self.get_json()

    @property
    def content(self):
        return self.get_data()


def authorize(client, settings, user_id=USER_A):
    client.delete_cookie(AUTH_COOKIE_NAME, domain="localhost")
    from app.services.sessions import start
    with client.application.app_context():
        with client.application.config["db_pool"].connection() as connection:
            tokens = client.application.config["auth_provider_factory"](settings).issue(user_id)
            token = start(connection, {"id": user_id}, tokens)
    client.set_cookie(
        AUTH_COOKIE_NAME,
        token,
        domain="localhost",
    )
    return client


def add(client, product_id=P1, quantity=1):
    return client.post("/api/cart/items", json={"product_id": str(product_id), "quantity": quantity})


def buy_now(client, product_id=P1, quantity=1):
    return client.post("/api/orders", json={
        "source": "buy_now", "product_id": str(product_id), "quantity": quantity, **SHIPPING,
    })


def checkout(client):
    return client.post("/api/orders", json={"source": "cart", **SHIPPING})


def pay(client, order_id, success=True):
    return client.post(f"/api/orders/{order_id}/payments", json={"simulate_success": success})


def assert_error(response, code):
    assert response.status_code == code, response.text
    assert response.json()["detail"]


def snapshot(store):
    return deepcopy(store.tables)
