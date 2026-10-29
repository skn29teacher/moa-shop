import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class QuantityRequest(RequestModel):
    quantity: StrictInt = Field(ge=1, le=2_147_483_647)


class CartAddRequest(QuantityRequest):
    product_id: UUID


class ShippingRequest(RequestModel):
    recipient_name: str = Field(min_length=1, max_length=100)
    recipient_phone: str = Field(min_length=1, max_length=30)
    shipping_address: str = Field(min_length=1, max_length=500)

    @field_validator("recipient_name", "recipient_phone", "shipping_address", mode="before")
    @classmethod
    def strip_shipping_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("recipient_phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        digits = len(re.sub(r"\D", "", value))
        if not re.fullmatch(r"\+?[0-9 ()-]+", value) or not 7 <= digits <= 15:
            raise ValueError("연락처는 숫자 7~15자리와 +, 공백, 괄호, -만 사용하세요.")
        return value


class CartOrderRequest(ShippingRequest):
    source: Literal["cart"]


class BuyNowOrderRequest(ShippingRequest):
    source: Literal["buy_now"]
    product_id: UUID
    quantity: StrictInt = Field(ge=1, le=2_147_483_647)


class OrderItemResponse(BaseModel):
    id: UUID
    product_id: UUID
    product_name: str
    quantity: int
    unit_price: int
    line_amount: int


class CartItemResponse(OrderItemResponse):
    stock: int


class CartResponse(BaseModel):
    id: UUID | None
    user_id: UUID
    status: Literal["cart"] = "cart"
    total_amount: int
    items: list[CartItemResponse]


class OrderResponse(BaseModel):
    id: UUID
    user_id: UUID
    status: Literal["pending", "paid"]
    total_amount: int
    recipient_name: str
    recipient_phone: str
    shipping_address: str
    ordered_at: datetime
    paid_at: datetime | None
    created_at: datetime
    items: list[OrderItemResponse]
