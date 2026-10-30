from uuid import UUID

from flask import Blueprint

from app.core.dependencies import get_current_user
from app.core.http import json_response, request_body, validate_value
from app.db.connection import get_connection
from app.schemas.orders import CartAddRequest, CartResponse, QuantityRequest
from app.services import cart as service


router = Blueprint("cart", __name__, url_prefix="/api/cart")


@router.get("")
def get_cart():
    user = get_current_user()
    return json_response(service.get_cart(get_connection(), user["id"]), CartResponse)


@router.post("/items")
def add_item():
    user = get_current_user()
    payload = request_body(CartAddRequest)
    result = service.add_item(
        get_connection(), user["id"], payload.product_id, payload.quantity
    )
    return json_response(result, CartResponse)


@router.patch("/items/<product_id>")
def change_quantity(product_id: str):
    user = get_current_user()
    product_id = validate_value(UUID, product_id, "path.product_id")
    payload = request_body(QuantityRequest)
    result = service.change_quantity(
        get_connection(), user["id"], product_id, payload.quantity
    )
    return json_response(result, CartResponse)


@router.delete("/items/<product_id>")
def remove_item(product_id: str):
    user = get_current_user()
    product_id = validate_value(UUID, product_id, "path.product_id")
    result = service.remove_item(get_connection(), user["id"], product_id)
    return json_response(result, CartResponse)
