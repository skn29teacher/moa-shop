from uuid import UUID

from flask import Blueprint

from app.core.dependencies import get_current_user
from app.core.http import json_response, request_body, validate_value
from app.db.connection import get_connection
from app.schemas.payments import MockPaymentRequest, PaymentResultResponse
from app.services import payments as service


router = Blueprint("payments", __name__, url_prefix="/api/orders")


@router.post("/<order_id>/payments")
def pay_order(order_id: str):
    user = get_current_user()
    order_id = validate_value(UUID, order_id, "path.order_id")
    payload = request_body(MockPaymentRequest)
    result, http_status = service.pay_order(
        get_connection(), user["id"], order_id, payload.simulate_success
    )
    return json_response(result, PaymentResultResponse, http_status)
