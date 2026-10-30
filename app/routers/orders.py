from typing import Annotated
from uuid import UUID

from flask import Blueprint
from pydantic import Field

from app.core.dependencies import get_current_user
from app.core.http import json_response, request_body, validate_value
from app.db.connection import get_connection
from app.schemas.orders import BuyNowOrderRequest, CartOrderRequest, OrderResponse
from app.services import orders as service


router = Blueprint("orders", __name__, url_prefix="/api/orders")
order_request = Annotated[
    CartOrderRequest | BuyNowOrderRequest,
    Field(discriminator="source"),
]


@router.post("")
def create_order():
    user = get_current_user()
    payload = request_body(order_request)
    result = service.create_order(get_connection(), user["id"], payload)
    return json_response(result, OrderResponse, 201)


@router.get("/<order_id>")
def get_order(order_id: str):
    user = get_current_user()
    order_id = validate_value(UUID, order_id, "path.order_id")
    result = service.get_order(get_connection(), user["id"], order_id)
    return json_response(result, OrderResponse)
