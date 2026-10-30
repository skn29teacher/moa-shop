import pytest

from app import main
from app.core import dependencies
from app.core.config import Settings
from tests.legacy_security import hash_password
from app.db import commerce, products, users
from app.services import auth, cart, orders, payments
from tests.memory import MemoryPool, MemoryRepository, MemoryStore
from tests.fake_auth import FakeAuth, install_sessions
from tests.support import FlaskTestResponse, ORIGIN, PASSWORD, authorize


@pytest.fixture(scope="session")
def password_hash():
    return hash_password(PASSWORD)


@pytest.fixture
def settings(tmp_path):
    # 실제 .env를 읽지 않습니다. 외부 접속에 사용할 수 없는 테스트 전용 설정입니다.
    return Settings(
        _env_file=None, app_origin=ORIGIN, database_path=tmp_path / "unit.sqlite3",
        secret_key="pytest-only-secret-" * 4, cookie_secure=False,
        supabase_url="https://auth.invalid", supabase_key="test-anon-key",
    )


@pytest.fixture
def store(monkeypatch, password_hash):
    store = MemoryStore(password_hash)
    repo = MemoryRepository(store)
    for module in (commerce, products, users):
        for name in vars(module).copy():
            if not name.startswith("_") and hasattr(repo, name):
                monkeypatch.setattr(module, name, getattr(repo, name))
    for user in store.tables['users'].values():
        user['auth_user_id'] = user['id']
        user['role'] = 'customer'
    monkeypatch.setattr(users, 'find_user_by_auth_id', lambda c, uid: next(
        (u for u in store.tables['users'].values() if u['auth_user_id'] == uid), None))
    install_sessions(monkeypatch, store)
    for module in (cart, orders, payments):
        monkeypatch.setattr(module, "lock_products", repo.lock_products)
    monkeypatch.setattr(payments, "decrease_stock", repo.decrease_stock)
    return store


@pytest.fixture
def pool(store):
    return MemoryPool(store)


@pytest.fixture
def client(monkeypatch, settings, pool):
    app = main.create_app(settings=settings, pool=pool)
    app.config["auth_provider_factory"] = lambda settings: FakeAuth(pool.store)
    app.response_class = FlaskTestResponse
    client = app.test_client()
    client.environ_base.update(
        HTTP_HOST="127.0.0.1:8000",
        HTTP_ORIGIN=ORIGIN,
    )
    yield client


@pytest.fixture
def buyer(client, settings):
    return authorize(client, settings)
