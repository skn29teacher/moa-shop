from uuid import UUID

from psycopg import Connection


def lock_member(connection: Connection, user_id: UUID) -> dict | None:
    # 회원 행 잠금으로 최초 장바구니 생성과 같은 회원의 변경 요청을 직렬화합니다.
    return connection.execute(
        "SELECT id, deleted_at FROM public.users WHERE id = %s FOR UPDATE",
        (user_id,),
    ).fetchone()


def find_cart(connection: Connection, user_id: UUID, *, lock: bool = False) -> dict | None:
    query = (
        "SELECT * FROM public.orders WHERE user_id = %s AND status = 'cart' FOR UPDATE"
        if lock else
        "SELECT * FROM public.orders WHERE user_id = %s AND status = 'cart'"
    )
    return connection.execute(query, (user_id,)).fetchone()


def insert_cart(connection: Connection, user_id: UUID) -> dict:
    return connection.execute(
        "INSERT INTO public.orders (user_id) VALUES (%s) RETURNING *",
        (user_id,),
    ).fetchone()


def find_owned_order(
    connection: Connection, order_id: UUID, user_id: UUID, *, lock: bool = False
) -> dict | None:
    query = (
        "SELECT * FROM public.orders WHERE id = %s AND user_id = %s FOR UPDATE"
        if lock else
        "SELECT * FROM public.orders WHERE id = %s AND user_id = %s"
    )
    return connection.execute(query, (order_id, user_id)).fetchone()


def list_user_orders(connection: Connection, user_id: UUID) -> list[dict]:
    # 장바구니는 구매내역에서 제외하고 최근 주문부터 반환합니다.
    return connection.execute(
        """
        SELECT * FROM public.orders
        WHERE user_id = %s AND status IN ('pending', 'paid')
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
        FROM public.order_items AS oi
        JOIN public.products AS p ON p.id = oi.product_id
        WHERE oi.order_id = %s ORDER BY oi.product_id
        """,
        (order_id,),
    ).fetchall()


def insert_item(connection: Connection, order_id: UUID, product: dict, quantity: int) -> None:
    connection.execute(
        """
        INSERT INTO public.order_items
            (order_id, product_id, product_name, quantity, unit_price)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (order_id, product["id"], product["name"], quantity, product["price"]),
    )


def update_quantity(connection: Connection, item_id: UUID, quantity: int) -> None:
    connection.execute(
        "UPDATE public.order_items SET quantity = %s, updated_at = now() WHERE id = %s",
        (quantity, item_id),
    )


def delete_item(connection: Connection, item_id: UUID) -> None:
    connection.execute("DELETE FROM public.order_items WHERE id = %s", (item_id,))


def calculate_total(connection: Connection, order_id: UUID) -> int:
    row = connection.execute(
        """
        SELECT COALESCE(SUM(quantity * unit_price), 0) AS total
        FROM public.order_items WHERE order_id = %s
        """,
        (order_id,),
    ).fetchone()
    return int(row["total"])


def update_cart_total(connection: Connection, order_id: UUID, total: int) -> dict:
    return connection.execute(
        "UPDATE public.orders SET total_amount = %s, updated_at = now() WHERE id = %s RETURNING *",
        (total, order_id),
    ).fetchone()


def confirm_item_price(connection: Connection, item_id: UUID, product: dict) -> None:
    connection.execute(
        """
        UPDATE public.order_items SET product_name = %s, unit_price = %s, updated_at = now()
        WHERE id = %s
        """,
        (product["name"], product["price"], item_id),
    )


def checkout_cart(connection: Connection, order_id: UUID, total: int, shipping: dict) -> dict:
    return connection.execute(
        """
        UPDATE public.orders
        SET status = 'pending', total_amount = %s, recipient_name = %s,
            recipient_phone = %s, shipping_address = %s, ordered_at = now(), updated_at = now()
        WHERE id = %s AND status = 'cart' RETURNING *
        """,
        (total, shipping["recipient_name"], shipping["recipient_phone"], shipping["shipping_address"], order_id),
    ).fetchone()


def insert_pending_order(connection: Connection, user_id: UUID, total: int, shipping: dict) -> dict:
    return connection.execute(
        """
        INSERT INTO public.orders
            (user_id, status, total_amount, recipient_name, recipient_phone, shipping_address, ordered_at)
        VALUES (%s, 'pending', %s, %s, %s, %s, now()) RETURNING *
        """,
        (user_id, total, shipping["recipient_name"], shipping["recipient_phone"], shipping["shipping_address"]),
    ).fetchone()


def find_successful_payment(connection: Connection, order_id: UUID) -> dict | None:
    return connection.execute(
        "SELECT * FROM public.payments WHERE order_id = %s AND status = 'success'",
        (order_id,),
    ).fetchone()


def insert_payment(
    connection: Connection, order_id: UUID, amount: int, *, success: bool, reason: str | None = None
) -> dict:
    return connection.execute(
        """
        INSERT INTO public.payments (order_id, amount, status, failure_reason)
        VALUES (%s, %s, %s, %s) RETURNING *
        """,
        (order_id, amount, "success" if success else "failed", reason),
    ).fetchone()


def mark_order_paid(connection: Connection, order_id: UUID) -> None:
    connection.execute(
        "UPDATE public.orders SET status = 'paid', paid_at = now(), updated_at = now() WHERE id = %s",
        (order_id,),
    )
