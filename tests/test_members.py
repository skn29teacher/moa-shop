from tests.support import P1, P2, PASSWORD, SHIPPING, USER_A, USER_B, add, authorize, buy_now, pay


def test_member_endpoints_require_login(client):
    assert client.get("/api/members/me").status_code == 401
    assert client.patch("/api/members/me", json={"name": "변경"}).status_code == 401
    assert client.put("/api/members/me/password", json={
        "current_password": PASSWORD, "new_password": "new-password-123",
    }).status_code == 401
    assert client.delete("/api/members/me").status_code == 401
    assert client.get("/api/members/me/orders").status_code == 401


def test_profile_read_and_partial_update_return_safe_fields(buyer, store):
    profile = buyer.get("/api/members/me")
    assert profile.status_code == 200
    assert profile.json()["id"] == str(USER_A)
    assert profile.json()["email"] == "buyer@example.com"
    assert "password_hash" not in profile.json()

    response = buyer.patch("/api/members/me", json={"name": "  새 이름  ", "phone": "010-1111-2222"})
    assert response.status_code == 200, response.text
    assert response.json()["name"] == "새 이름"
    assert response.json()["phone"] == "010-1111-2222"
    assert response.json()["address"] is None
    assert store.tables["users"][USER_A]["name"] == "새 이름"

    cleared = buyer.patch("/api/members/me", json={"phone": "", "address": "서울시 수정 주소"})
    assert cleared.status_code == 200
    assert cleared.json()["phone"] is None
    assert cleared.json()["address"] == "서울시 수정 주소"


def test_profile_patch_rejects_empty_or_invalid_updates_without_changes(buyer, store):
    before = store.tables["users"][USER_A].copy()
    for body in ({}, {"name": " "}, {"name": None}, {"phone": "123"}, {"unexpected": "x"}):
        response = buyer.patch("/api/members/me", json=body)
        assert response.status_code == 422, response.text
        assert store.tables["users"][USER_A] == before


def test_password_change_requires_current_password_and_updates_hash(buyer, store):
    old_hash = store.tables["users"][USER_A]["password_hash"]
    wrong = buyer.put("/api/members/me/password", json={
        "current_password": "wrong-password", "new_password": "Updated-password-2026!",
    })
    assert wrong.status_code == 400
    assert store.tables["users"][USER_A]["password_hash"] == old_hash

    changed = buyer.put("/api/members/me/password", json={
        "current_password": PASSWORD, "new_password": "Updated-password-2026!",
    })
    assert changed.status_code == 204
    assert changed.content == b""
    assert store.tables["users"][USER_A]["password_hash"] != old_hash
    assert buyer.post("/api/auth/login", json={"email": "buyer@example.com", "password": PASSWORD}).status_code == 401
    assert buyer.post("/api/auth/login", json={
        "email": "buyer@example.com", "password": "Updated-password-2026!",
    }).status_code == 200


def test_password_change_rejects_invalid_input_without_changing_hash(buyer, store):
    old_hash = store.tables["users"][USER_A]["password_hash"]
    for body in (
        {"current_password": PASSWORD, "new_password": "short"},
        {"current_password": "", "new_password": "Updated-password-2026!"},
        {"current_password": PASSWORD, "new_password": "Updated-password-2026!", "extra": True},
    ):
        response = buyer.put("/api/members/me/password", json=body)
        assert response.status_code == 422
        assert store.tables["users"][USER_A]["password_hash"] == old_hash


def test_purchase_history_excludes_cart_and_is_scoped_to_member(client, settings, buyer):
    add(buyer, P1, 1)
    assert buyer.get("/api/members/me/orders").json() == []
    pending = buy_now(buyer, P1, 2).json()
    paid_order = buy_now(buyer, P2, 1).json()
    assert pay(buyer, paid_order["id"], success=True).status_code == 200

    response = buyer.get("/api/members/me/orders")
    assert response.status_code == 200, response.text
    rows = response.json()
    assert [item["id"] for item in rows] == [paid_order["id"], pending["id"]]
    assert {item["status"] for item in rows} == {"pending", "paid"}
    assert all(item["items"] for item in rows)

    other = authorize(client, settings, USER_B)
    assert other.get("/api/members/me/orders").json() == []


def test_soft_delete_preserves_orders_and_blocks_existing_session(buyer, store):
    order = buy_now(buyer, P1, 1).json()
    response = buyer.delete("/api/members/me")
    assert response.status_code == 204
    assert response.content == b""
    assert "shop_access_token" in response.headers["set-cookie"]
    assert store.tables["users"][USER_A]["deleted_at"] is not None
    assert order["id"] in {str(row["id"]) for row in store.tables["orders"].values()}
    assert buyer.get("/api/members/me").status_code == 401
    assert buyer.get("/api/members/me/orders").status_code == 401
    assert buyer.post("/api/auth/login", json={"email": "buyer@example.com", "password": PASSWORD}).status_code == 401
