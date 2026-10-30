"""DBアクセス境界のテスト用代替。PostgreSQLの制約・ロック検証には使いません。"""

from contextlib import contextmanager
from copy import deepcopy
from threading import RLock
from uuid import uuid4

from psycopg import OperationalError
from psycopg.errors import UniqueViolation

from tests.support import seed_rows, utcnow


class MemoryStore:
    def __init__(self, password_hash):
        self.tables = seed_rows(password_hash)
        self.lock = RLock()
        self.fail_commit_once = False
        self.commits = 0
        self.rollbacks = 0

    @property
    def sessions(self):
        return self.tables["sessions"]

    def connect(self):
        return MemoryConnection(self)


class MemoryConnection:
    def __init__(self, store):
        self.store = store

    @contextmanager
    def transaction(self):
        # サービスの一括変更・失敗時復元を検証する代替です。実DBのロックではありません。
        with self.store.lock:
            before = deepcopy(self.store.tables)
            try:
                yield
                if self.store.fail_commit_once:
                    self.store.fail_commit_once = False
                    raise OperationalError("simulated commit failure")
                self.store.commits += 1
            except BaseException:
                self.store.tables = before
                self.store.rollbacks += 1
                raise

    def execute(self, *args, **kwargs):
        raise AssertionError("オフライン検証中に未差し替えのSQLが実行されました。")


class MemoryPool:
    def __init__(self, store):
        self.store = store
        self.opened = False
        self.closed = False

    def open(self, **kwargs):
        self.opened = True

    def close(self):
        self.closed = True

    @contextmanager
    def connection(self):
        yield self.store.connect()


class MemoryRepository:
    """SQL은 교체하지만 라우터·JWT·검증·구매 서비스는 실제 코드를 사용합니다."""

    def __init__(self, store):
        self.store = store

    def _table(self, name):
        return self.store.tables[name]

    def find_user_by_email(self, connection, email):
        return next((deepcopy(u) for u in self._table("users").values() if u["email"] == email), None)

    def find_user_by_id(self, connection, user_id):
        return deepcopy(self._table("users").get(user_id))

    def insert_user(self, connection, **values):
        if any(u["email"] == values["email"] for u in self._table("users").values()):
            raise UniqueViolation("duplicate test email")
        user = dict(id=uuid4(), **values, deleted_at=None, created_at=utcnow(), updated_at=utcnow())
        self._table("users")[user["id"]] = user
        return deepcopy(user)

    def update_profile(self, connection, user_id, *, name, phone, address):
        user = self._table("users").get(user_id)
        if user is None or user["deleted_at"] is not None:
            return None
        user.update(name=name, phone=phone, address=address, updated_at=utcnow())
        return {key: deepcopy(user[key]) for key in ("id", "email", "name", "phone", "address", "created_at")}

    def find_password_hash_for_update(self, connection, user_id):
        user = self._table("users").get(user_id)
        return deepcopy({"password_hash": user["password_hash"], "deleted_at": user["deleted_at"]}) if user else None

    def update_password_hash(self, connection, user_id, password_hash):
        user = self._table("users").get(user_id)
        if user is None or user["deleted_at"] is not None:
            return False
        user.update(password_hash=password_hash, updated_at=utcnow())
        return True

    def soft_delete_user(self, connection, user_id):
        user = self._table("users").get(user_id)
        if user is None or user["deleted_at"] is not None:
            return False
        user.update(deleted_at=utcnow(), updated_at=utcnow())
        return True

    def lock_member(self, connection, user_id):
        return self.find_user_by_id(connection, user_id)

    def list_products(self, connection, limit, offset):
        return deepcopy(sorted(self._table("products").values(), key=lambda p: (p["created_at"], p["id"]))[offset:offset + limit])

    def count_products(self, connection):
        return len(self._table("products"))

    def find_product(self, connection, product_id):
        return deepcopy(self._table("products").get(product_id))

    def lock_products(self, connection, product_ids):
        return {key: deepcopy(self._table("products")[key]) for key in sorted(set(product_ids))
                if key in self._table("products")}

    def decrease_stock(self, connection, product_id, quantity):
        product = self._table("products").get(product_id)
        if product is None or product["stock"] < quantity:
            return False
        product["stock"] -= quantity
        product["updated_at"] = utcnow()
        return True

    def find_cart(self, connection, user_id, *, lock=False):
        return next((deepcopy(o) for o in self._table("orders").values()
                     if o["user_id"] == user_id and o["status"] == "cart"), None)

    def insert_cart(self, connection, user_id):
        order = dict(id=uuid4(), user_id=user_id, status="cart", total_amount=0,
                     recipient_name=None, recipient_phone=None, shipping_address=None,
                     ordered_at=None, paid_at=None, created_at=utcnow(), updated_at=utcnow())
        self._table("orders")[order["id"]] = order
        return deepcopy(order)

    def find_owned_order(self, connection, order_id, user_id, *, lock=False):
        order = self._table("orders").get(order_id)
        return deepcopy(order) if order and order["user_id"] == user_id else None

    def list_user_orders(self, connection, user_id):
        orders = [o for o in self._table("orders").values()
                  if o["user_id"] == user_id and o["status"] in {"pending", "paid"}]
        return deepcopy(sorted(orders, key=lambda o: (o["ordered_at"], o["created_at"], str(o["id"])), reverse=True))

    def list_items(self, connection, order_id):
        result = []
        for item in sorted(self._table("items").values(), key=lambda item: item["product_id"]):
            product = self._table("products").get(item["product_id"])
            if item["order_id"] == order_id and product:
                result.append(dict(deepcopy(item), line_amount=item["quantity"] * item["unit_price"], stock=product["stock"]))
        return result

    def insert_item(self, connection, order_id, product, quantity):
        item = dict(id=uuid4(), order_id=order_id, product_id=product["id"],
                    product_name=product["name"], quantity=quantity, unit_price=product["price"],
                    created_at=utcnow(), updated_at=utcnow())
        self._table("items")[item["id"]] = item

    def update_quantity(self, connection, item_id, quantity):
        self._table("items")[item_id].update(quantity=quantity, updated_at=utcnow())

    def delete_item(self, connection, item_id):
        del self._table("items")[item_id]

    def calculate_total(self, connection, order_id):
        return sum(i["quantity"] * i["unit_price"] for i in self._table("items").values() if i["order_id"] == order_id)

    def update_cart_total(self, connection, order_id, total):
        self._table("orders")[order_id].update(total_amount=total, updated_at=utcnow())
        return deepcopy(self._table("orders")[order_id])

    def confirm_item_price(self, connection, item_id, product):
        self._table("items")[item_id].update(product_name=product["name"], unit_price=product["price"], updated_at=utcnow())

    def checkout_cart(self, connection, order_id, total, shipping):
        self._table("orders")[order_id].update(status="pending", total_amount=total, **shipping,
                                               ordered_at=utcnow(), updated_at=utcnow())
        return deepcopy(self._table("orders")[order_id])

    def insert_pending_order(self, connection, user_id, total, shipping):
        order = self.insert_cart(connection, user_id)
        return self.checkout_cart(connection, order["id"], total, shipping)

    def find_successful_payment(self, connection, order_id):
        return next((deepcopy(p) for p in self._table("payments").values()
                     if p["order_id"] == order_id and p["status"] == "success"), None)

    def insert_payment(self, connection, order_id, amount, *, success, reason=None):
        if success and self.find_successful_payment(connection, order_id):
            raise UniqueViolation("duplicate successful payment")
        payment = dict(id=uuid4(), order_id=order_id, amount=amount,
                       status="success" if success else "failed", failure_reason=reason, created_at=utcnow())
        self._table("payments")[payment["id"]] = payment
        return deepcopy(payment)

    def mark_order_paid(self, connection, order_id):
        self._table("orders")[order_id].update(status="paid", paid_at=utcnow(), updated_at=utcnow())
