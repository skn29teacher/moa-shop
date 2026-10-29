from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, status

from app.core.dependencies import CurrentUser, DatabaseConnection
from app.schemas.orders import BuyNowOrderRequest, CartOrderRequest, OrderResponse
from app.services import orders as service


router = APIRouter(prefix="/api/orders", tags=["주문"])


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(
    payload: Annotated[CartOrderRequest | BuyNowOrderRequest, Body(discriminator="source")],
    user: CurrentUser,
    connection: DatabaseConnection,
):
    """source=cart는 장바구니 전체, buy_now는 선택한 상품으로 주문을 만듭니다."""
    return service.create_order(connection, user["id"], payload)


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(order_id: UUID, user: CurrentUser, connection: DatabaseConnection):
    """결제 화면에 필요한 본인 주문의 확정 정보를 조회합니다."""
    return service.get_order(connection, user["id"], order_id)
