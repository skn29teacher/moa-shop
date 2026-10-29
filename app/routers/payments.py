from uuid import UUID

from fastapi import APIRouter, Response

from app.core.dependencies import CurrentUser, DatabaseConnection
from app.schemas.payments import MockPaymentRequest, PaymentResultResponse
from app.services import payments as service


router = APIRouter(prefix="/api/orders", tags=["모의 결제"])


@router.post(
    "/{order_id}/payments",
    response_model=PaymentResultResponse,
    responses={409: {"description": "재고 부족(실패 결제 결과) 또는 주문 정보 충돌"}},
)
def pay_order(
    order_id: UUID,
    payload: MockPaymentRequest,
    response: Response,
    user: CurrentUser,
    connection: DatabaseConnection,
):
    """모의 결과를 지정합니다. 금액은 서버에서 결정하고 성공한 주문은 재결제하지 않습니다."""
    result, http_status = service.pay_order(connection, user["id"], order_id, payload.simulate_success)
    response.status_code = http_status
    return result
