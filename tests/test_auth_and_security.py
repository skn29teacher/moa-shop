from http.cookies import SimpleCookie
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.security import AUTH_COOKIE_NAME, authentication_error
from tests.legacy_security import hash_password, verify_password
from app.schemas.auth import SignupRequest
from tests.support import ORIGIN, P1, PASSWORD, USER_A, snapshot, utcnow


@pytest.mark.parametrize("bad_origin", ["", "localhost", "ftp://store.test", "https:///missing-host",
                                         "http://store.test/path", "https://user:pass@store.test",
                                         "http://store.test?x=1", "http://store.test#frag"])
def test_settings_reject_invalid_app_origin(bad_origin):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_origin=bad_origin,
                 database_path="instance/test-only.sqlite3", secret_key="x" * 48)


def test_settings_reject_bad_database_path_and_short_secret():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_origin=ORIGIN, database_path="mysql://x",
                 secret_key="x" * 48)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_origin=ORIGIN,
                 database_path="instance/test-only.sqlite3", secret_key="x" * 31)


def test_https_requires_secure_cookie_and_lifetime_is_bounded():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_origin="https://store.test",
                 database_path="instance/test-only.sqlite3", secret_key="x" * 48,
                 cookie_secure=False)
    for days in (0, 31):
        with pytest.raises(ValidationError):
            Settings(_env_file=None, app_origin=ORIGIN,
                     database_path="instance/test-only.sqlite3", secret_key="x" * 48,
                     session_days=days)


def test_password_hash_is_argon2_and_verifies_only_matching_password():
    encoded = hash_password(PASSWORD)
    assert encoded.startswith("$argon2id$")
    assert verify_password(PASSWORD, encoded) is True
    assert verify_password("wrong-password", encoded) is False
    assert verify_password(PASSWORD, "malformed-hash") is False


def test_signup_normalizes_email_name_and_optional_fields():
    signup = SignupRequest(email="  Buyer@Example.COM ", password=PASSWORD, name=" 김테스트 ", phone="   ", address="   ")
    assert str(signup.email) == "buyer@example.com"
    assert signup.name == "김테스트"
    assert signup.phone is None
    assert signup.address is None


@pytest.mark.parametrize("overrides", [
    {"email": "not-an-email"}, {"email": "x" * 245 + "@example.com"},
    {"password": "short7!"}, {"password": "x" * 129},
    {"name": " "}, {"name": "x" * 101}, {"phone": "123"},
    {"phone": "010-1234-5678 ext. 4"}, {"address": "x" * 501},
    {"unexpected": "field"}, {"password": True},
])
def test_signup_rejects_invalid_fields(overrides):
    data = dict(email="buyer@example.com", password=PASSWORD, name="Test", phone=None, address=None)
    data.update(overrides)
    with pytest.raises(ValidationError):
        SignupRequest.model_validate(data)


def test_signup_accepts_phone_with_international_prefix():
    signup = SignupRequest(email="buyer@example.com", password=PASSWORD, name="Test", phone="+82 (10) 1234-5678")
    assert signup.phone == "+82 (10) 1234-5678"


def test_auth_error_is_generic():
    error = authentication_error()
    assert error.status_code == 401
    assert "로그인이 필요" in error.detail


def test_signup_returns_generic_message_for_new_and_duplicate_emails(client, store):
    response = client.post("/api/auth/signup", json={
        "email": " New.User@Example.com ", "password": PASSWORD,
        "name": "새 회원", "phone": "", "address": "",
    })
    assert response.status_code == 202, response.text
    user = response.json()
    assert "message" in user
    assert "password" not in user and "password_hash" not in user
    saved = next(u for u in store.tables["users"].values() if u["email"] == "new.user@example.com")
    assert saved["password_hash"].startswith("$argon2id$")
    duplicate = client.post("/api/auth/signup", json={
        "email": "NEW.USER@example.com", "password": PASSWORD, "name": "다른 이름",
    })
    assert duplicate.status_code == 202
    assert duplicate.json() == user


@pytest.mark.parametrize("body", [
    {"email": "bad", "password": "secret-visible-input", "name": "테스트"},
    {"email": "valid@example.com", "password": "short", "name": "테스트"},
    {"email": "valid@example.com", "password": "long-enough-password", "name": "  "},
    {"email": "valid@example.com", "password": "long-enough-password", "name": "테스트", "phone": "12"},
    {"email": "valid@example.com", "password": "long-enough-password", "name": "테스트", "extra": "x"},
])
def test_signup_api_validation_redacts_password(client, body):
    response = client.post("/api/auth/signup", json=body)
    assert response.status_code == 422
    assert "secret-visible-input" not in response.text
    assert "input" not in response.json()["errors"][0]


def test_login_sets_secure_cookie_without_token_in_json(client, settings):
    response = client.post("/api/auth/login", json={"email": "BUYER@example.com", "password": PASSWORD})
    assert response.status_code == 200, response.text
    assert response.json()["user"]["id"] == str(USER_A)
    assert "access_token" not in response.json()
    cookie = SimpleCookie(response.headers["set-cookie"])[AUTH_COOKIE_NAME]
    assert cookie["httponly"] is True
    # Secure=false 쿠키는 보통 Set-Cookie에서 Secure 속성을 생략합니다.
    assert cookie["secure"] == ""
    assert cookie["samesite"].lower() == "lax"
    assert cookie["path"] == "/"


@pytest.mark.parametrize("email,password", [
    ("buyer@example.com", "wrong"), ("unknown@example.com", PASSWORD),
])
def test_login_wrong_password_or_missing_email_has_same_response(client, email, password):
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 401
    assert "이메일 또는 비밀번호" in response.json()["detail"]
    assert "set-cookie" not in response.headers


def test_login_rejects_soft_deleted_account(client, store):
    store.tables["users"][USER_A]["deleted_at"] = utcnow()
    response = client.post("/api/auth/login", json={"email": "buyer@example.com", "password": PASSWORD})
    assert response.status_code == 401


def test_existing_token_is_rejected_after_soft_delete(buyer, store):
    store.tables["users"][USER_A]["deleted_at"] = utcnow()
    response = buyer.get("/api/cart")
    assert response.status_code == 401


def test_logout_is_idempotent_and_deletes_auth_cookie(client):
    response = client.post("/api/auth/logout")
    assert response.status_code == 204
    assert response.content == b""
    cleared = SimpleCookie(response.headers["set-cookie"])[AUTH_COOKIE_NAME]
    assert cleared.value == ""
    assert cleared["max-age"] == "0"
    assert cleared["httponly"] is True
    assert client.get("/api/cart").status_code == 401
    assert client.post("/api/auth/logout").status_code == 204


def test_mutating_request_requires_same_origin(client, store):
    before = snapshot(store)
    response = client.post("/api/cart/items", json={"product_id": str(P1), "quantity": 1},
                           headers={"Origin": "https://attacker.test"})
    assert response.status_code == 403
    assert store.tables == before


def test_cross_site_fetch_is_rejected_even_with_matching_origin(buyer, store):
    before = snapshot(store)
    response = buyer.post("/api/cart/items", json={"product_id": str(P1), "quantity": 1},
                          headers={"Sec-Fetch-Site": "cross-site"})
    assert response.status_code == 403
    assert snapshot(store) == before
