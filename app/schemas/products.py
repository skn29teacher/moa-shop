from uuid import UUID

from pydantic import BaseModel


class ProductResponse(BaseModel):
    id: UUID
    name: str
    description: str
    price: int
    stock: int


class ProductListResponse(BaseModel):
    items: list[ProductResponse]
    total: int
    limit: int
    offset: int
