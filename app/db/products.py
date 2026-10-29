from uuid import UUID

from psycopg import Connection


def list_products(connection: Connection, limit: int, offset: int) -> list[dict]:
    return connection.execute(
        """
        SELECT id, name, description, price, stock
        FROM public.products ORDER BY created_at, id LIMIT %s OFFSET %s
        """,
        (limit, offset),
    ).fetchall()


def count_products(connection: Connection) -> int:
    return connection.execute("SELECT count(*) AS total FROM public.products").fetchone()["total"]


def find_product(connection: Connection, product_id: UUID) -> dict | None:
    return connection.execute(
        "SELECT id, name, description, price, stock FROM public.products WHERE id = %s",
        (product_id,),
    ).fetchone()


def lock_products(connection: Connection, product_ids: list[UUID]) -> dict[UUID, dict]:
    if not product_ids:
        return {}
    # 모든 구매 경로에서 같은 ID 순서로 잠가 상품 간 교착 가능성을 줄입니다.
    rows = connection.execute(
        """
        SELECT id, name, price, stock FROM public.products
        WHERE id = ANY(%s::uuid[]) ORDER BY id FOR UPDATE
        """,
        (product_ids,),
    ).fetchall()
    return {row["id"]: row for row in rows}


def decrease_stock(connection: Connection, product_id: UUID, quantity: int) -> bool:
    row = connection.execute(
        """
        UPDATE public.products SET stock = stock - %s, updated_at = now()
        WHERE id = %s AND stock >= %s RETURNING id
        """,
        (quantity, product_id, quantity),
    ).fetchone()
    return row is not None
