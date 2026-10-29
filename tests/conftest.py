import pytest
from fastapi.testclient import TestClient

from app import main
from app.core import dependencies
from app.core.config import Settings
from app.core.security import hash_password
from app.db import commerce, products, users
from app.services import auth, cart, orders, payments
from tests.memory import MemoryPool, MemoryRepository, MemoryStore
from tests.support import ORIGIN, PASSWORD, authorize


@pytest.fixture(scope="session")
def password_hash():
    return hash_password(PASSWORD)


@pytest.fixture
def settings():
    # 실제 .env를 읽지 않습니다. 외부 접속에 사용할 수 없는 테스트 전용 설정입니다.
    return Settings(
        _env_file=None, app_origin=ORIGIN, database_url="postgresql://test@invalid/test_only",
        secret_key="pytest-only-secret-" * 4, cookie_secure=False,
        access_token_expire_minutes=60, supabase_url=None, supabase_key=None,
    )


@pytest.fixture
def store(monkeypatch, password_hash):
    store = MemoryStore(password_hash)
    repo = MemoryRepository(store)
    for module in (commerce, products, users):
        for name in vars(module).copy():
            if not name.startswith("_") and hasattr(repo, name):
                monkeypatch.setattr(module, name, getattr(repo, name))
    # from ... import 형태로 가져간 경계도 함께 교체합니다.
    monkeypatch.setattr(auth, "find_user_by_email", repo.find_user_by_email)
    monkeypatch.setattr(auth, "insert_user", repo.insert_user)
    monkeypatch.setattr(dependencies, "find_user_by_id", repo.find_user_by_id)
    for module in (cart, orders, payments):
        monkeypatch.setattr(module, "lock_products", repo.lock_products)
    monkeypatch.setattr(payments, "decrease_stock", repo.decrease_stock)
    return store


@pytest.fixture
def pool(store):
    return MemoryPool(store)


@pytest.fixture
def client(monkeypatch, settings, pool):
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    monkeypatch.setattr(main, "create_pool", lambda _: pool)
    with TestClient(main.app, base_url=ORIGIN, headers={"Origin": ORIGIN}) as client:
        yield client


@pytest.fixture
def buyer(client, settings):
    return authorize(client, settings)
