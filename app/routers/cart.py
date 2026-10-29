from uuid import UUID

from fastapi import APIRouter

from app.core.dependencies import CurrentUser, DatabaseConnection
from app.schemas.orders import CartAddRequest, CartResponse, QuantityRequest
from app.services import cart as service


router = APIRouter(prefix="/api/cart", tags=["장바구니"])


@router.get("", response_model=CartResponse)
def get_cart(user: CurrentUser, connection: DatabaseConnection):
    return service.get_cart(connection, user["id"])


@router.post("/items", response_model=CartResponse)
def add_item(payload: CartAddRequest, user: CurrentUser, connection: DatabaseConnection):
    """이미 담긴 상품이면 요청 수량을 더합니다. 재고는 차감하지 않습니다."""
    return service.add_item(connection, user["id"], payload.product_id, payload.quantity)


@router.patch("/items/{product_id}", response_model=CartResponse)
def change_quantity(
    product_id: UUID, payload: QuantityRequest, user: CurrentUser, connection: DatabaseConnection
):
    """상품 ID를 경로에 넣고 수량을 새 값으로 설정합니다. 0은 삭제가 아니라 422입니다."""
    return service.change_quantity(connection, user["id"], product_id, payload.quantity)


@router.delete("/items/{product_id}", response_model=CartResponse)
def remove_item(product_id: UUID, user: CurrentUser, connection: DatabaseConnection):
    """본인 cart의 상품만 삭제하고 갱신된 장바구니를 반환합니다."""
    return service.remove_item(connection, user["id"], product_id)
