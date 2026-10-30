from uuid import UUID, uuid4

from app.db.connection import Connection


def lock_member(connection: Connection, user_id: UUID) -> dict | None:
    # 호출 서비스의 BEGIN IMMEDIATE 트랜잭션 안에서 활성 회원을 확인합니다.
    return connection.execute(
        "SELECT id, deleted_at FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()


def find_cart(connection: Connection, user_id: UUID, *, lock: bool = False) -> dict | None:
    query = (
        "SELECT * FROM orders WHERE user_id = ? AND status = 'cart'"
        if lock else
        "SELECT * FROM orders WHERE user_id = ? AND status = 'cart'"
    )
    return connection.execute(query, (user_id,)).fetchone()


def insert_cart(connection: Connection, user_id: UUID) -> dict:
    return connection.execute(
        "INSERT INTO orders (id, user_id) VALUES (?, ?) RETURNING *",
        (uuid4(), user_id),
    ).fetchone()


def find_owned_order(
    connection: Connection, order_id: UUID, user_id: UUID, *, lock: bool = False
) -> dict | None:
    query = (
        "SELECT * FROM orders WHERE id = ? AND user_id = ?"
        if lock else
        "SELECT * FROM orders WHERE id = ? AND user_id = ?"
    )
    return connection.execute(query, (order_id, user_id)).fetchone()


def list_user_orders(connection: Connection, user_id: UUID) -> list[dict]:
    # 장바구니는 구매내역에서 제외하고 최근 주문부터 반환합니다.
    return connection.execute(
        """
        SELECT * FROM orders
        WHERE user_id = ? AND status IN ('pending', 'paid')
        ORDER BY ordered_at DESC, created_at DESC, id DESC
        """,
        (user_id,),
    ).fetchall()


def list_items(connection: Connection, order_id: UUID) -> list[dict]:
    return connection.execute(
        """
        SELECT oi.id, oi.order_id, oi.product_id, oi.product_name,
               oi.quantity, oi.unit_price, oi.quantity * oi.unit_price AS line_amount,
               p.stock
        FROM order_items AS oi
        JOIN products AS p ON p.id = oi.product_id
        WHERE oi.order_id = ? ORDER BY oi.product_id
        """,
        (order_id,),
    ).fetchall()


def insert_item(connection: Connection, order_id: UUID, product: dict, quantity: int) -> None:
    connection.execute(
        """
        INSERT INTO order_items
            (id, order_id, product_id, product_name, quantity, unit_price)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (uuid4(), order_id, product["id"], product["name"], quantity, product["price"]),
    )


def update_quantity(connection: Connection, item_id: UUID, quantity: int) -> None:
    connection.execute(
        "UPDATE order_items SET quantity = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = ?",
        (quantity, item_id),
    )


def delete_item(connection: Connection, item_id: UUID) -> None:
    connection.execute("DELETE FROM order_items WHERE id = ?", (item_id,))


def calculate_total(connection: Connection, order_id: UUID) -> int:
    row = connection.execute(
        """
        SELECT COALESCE(SUM(quantity * unit_price), 0) AS total
        FROM order_items WHERE order_id = ?
        """,
        (order_id,),
    ).fetchone()
    return int(row["total"])


def update_cart_total(connection: Connection, order_id: UUID, total: int) -> dict:
    return connection.execute(
        "UPDATE orders SET total_amount = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = ? RETURNING *",
        (total, order_id),
    ).fetchone()


def confirm_item_price(connection: Connection, item_id: UUID, product: dict) -> None:
    connection.execute(
        """
        UPDATE order_items SET product_name = ?, unit_price = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
        WHERE id = ?
        """,
        (product["name"], product["price"], item_id),
    )


def checkout_cart(connection: Connection, order_id: UUID, total: int, shipping: dict) -> dict:
    return connection.execute(
        """
        UPDATE orders
        SET status = 'pending', total_amount = ?, recipient_name = ?,
            recipient_phone = ?, shipping_address = ?, ordered_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
        WHERE id = ? AND status = 'cart' RETURNING *
        """,
        (total, shipping["recipient_name"], shipping["recipient_phone"], shipping["shipping_address"], order_id),
    ).fetchone()


def insert_pending_order(connection: Connection, user_id: UUID, total: int, shipping: dict) -> dict:
    return connection.execute(
        """
        INSERT INTO orders
            (id, user_id, status, total_amount, recipient_name, recipient_phone, shipping_address, ordered_at)
        VALUES (?, ?, 'pending', ?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now')) RETURNING *
        """,
        (uuid4(), user_id, total, shipping["recipient_name"], shipping["recipient_phone"], shipping["shipping_address"]),
    ).fetchone()


def find_successful_payment(connection: Connection, order_id: UUID) -> dict | None:
    return connection.execute(
        "SELECT * FROM payments WHERE order_id = ? AND status = 'success'",
        (order_id,),
    ).fetchone()


def insert_payment(
    connection: Connection, order_id: UUID, amount: int, *, success: bool, reason: str | None = None
) -> dict:
    return connection.execute(
        """
        INSERT INTO payments (id, order_id, amount, status, failure_reason)
        VALUES (?, ?, ?, ?, ?) RETURNING *
        """,
        (uuid4(), order_id, amount, "success" if success else "failed", reason),
    ).fetchone()


def mark_order_paid(connection: Connection, order_id: UUID) -> None:
    connection.execute(
        "UPDATE orders SET status = 'paid', paid_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = ?",
        (order_id,),
    )
