from uuid import UUID

from app.db.connection import Connection


def list_products(connection: Connection, limit: int, offset: int) -> list[dict]:
    return connection.execute(
        """
        SELECT id, name, description, price, stock
        FROM products ORDER BY created_at, id LIMIT ? OFFSET ?
        """,
        (limit, offset),
    ).fetchall()


def count_products(connection: Connection) -> int:
    return connection.execute("SELECT count(*) AS total FROM products").fetchone()["total"]


def find_product(connection: Connection, product_id: UUID) -> dict | None:
    return connection.execute(
        "SELECT id, name, description, price, stock FROM products WHERE id = ?",
        (product_id,),
    ).fetchone()


def lock_products(connection: Connection, product_ids: list[UUID]) -> dict[UUID, dict]:
    if not product_ids:
        return {}
    # BEGIN IMMEDIATE already owns SQLite's write reservation before these reads.
    placeholders = ','.join('?' for _ in product_ids)
    rows = connection.execute(
        f"SELECT id, name, price, stock FROM products WHERE id IN ({placeholders}) ORDER BY id",
        product_ids,
    ).fetchall()
    return {row["id"]: row for row in rows}


def decrease_stock(connection: Connection, product_id: UUID, quantity: int) -> bool:
    row = connection.execute(
        """
        UPDATE products SET stock = stock - ?, updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
        WHERE id = ? AND stock >= ? RETURNING id
        """,
        (quantity, product_id, quantity),
    ).fetchone()
    return row is not None
