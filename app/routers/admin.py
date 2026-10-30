from uuid import UUID

from flask import Blueprint, request
from pydantic import Field
from typing import Annotated

from app.core.dependencies import require_admin
from app.core.errors import HTTPException
from app.core.http import json_response, request_body, validate_value
from app.db.connection import get_connection
from app.schemas.products import ProductResponse, ProductWriteRequest
from app.schemas.orders import OrderResponse
from app.services.commerce_common import order_snapshot


router = Blueprint('admin', __name__, url_prefix='/api/admin')


@router.post('/products')
def create_product():
    require_admin()
    payload = request_body(ProductWriteRequest)
    connection = get_connection()
    with connection.transaction():
        row = connection.execute('''INSERT INTO public.products (name, description, price, stock)
            VALUES (%s, %s, %s, %s) RETURNING id, name, description, price, stock''',
            (payload.name, payload.description, payload.price, payload.stock)).fetchone()
    return json_response(row, ProductResponse, 201)


@router.put('/products/<product_id>')
def update_product(product_id):
    require_admin()
    product_id = validate_value(UUID, product_id, 'path.product_id')
    payload = request_body(ProductWriteRequest)
    connection = get_connection()
    with connection.transaction():
        row = connection.execute('''UPDATE public.products SET name=%s, description=%s,
            price=%s, stock=%s, updated_at=now() WHERE id=%s
            RETURNING id, name, description, price, stock''',
            (payload.name, payload.description, payload.price, payload.stock, product_id)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='상품을 찾을 수 없습니다.')
    return json_response(row, ProductResponse)


@router.get('/orders')
def list_orders():
    require_admin()
    limit = validate_value(Annotated[int, Field(ge=1, le=100)], request.args.get('limit', '20'), 'query.limit')
    offset = validate_value(Annotated[int, Field(ge=0)], request.args.get('offset', '0'), 'query.offset')
    connection = get_connection()
    with connection.transaction():
        rows = connection.execute('''SELECT * FROM public.orders WHERE status <> 'cart'
            ORDER BY created_at DESC, id LIMIT %s OFFSET %s''', (limit, offset)).fetchall()
        result = [order_snapshot(connection, row) for row in rows]
    return json_response(result, list[OrderResponse])
