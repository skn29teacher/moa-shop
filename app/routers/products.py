from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.core.dependencies import DatabaseConnection
from app.schemas.products import ProductListResponse, ProductResponse
from app.services import products as service


router = APIRouter(prefix="/api/products", tags=["상품"])


@router.get("", response_model=ProductListResponse)
def list_products(
    connection: DatabaseConnection,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """로그인 없이 조회합니다. 품절 상품도 목록에 표시합니다."""
    return service.list_products(connection, limit, offset)


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(product_id: UUID, connection: DatabaseConnection):
    return service.get_product(connection, product_id)
