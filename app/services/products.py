from uuid import UUID

from psycopg import Connection

from app.core.errors import HTTPException
from app.db import products as db


def list_products(connection: Connection, limit: int, offset: int) -> dict:
    return {
        "items": db.list_products(connection, limit, offset),
        "total": db.count_products(connection),
        "limit": limit,
        "offset": offset,
    }


def get_product(connection: Connection, product_id: UUID) -> dict:
    product = db.find_product(connection, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다.")
    return product
