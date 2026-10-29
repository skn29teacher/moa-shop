from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StrictBool


class MockPaymentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    simulate_success: StrictBool = True


class PaymentResponse(BaseModel):
    id: UUID
    order_id: UUID
    amount: int
    status: Literal["success", "failed"]
    failure_reason: str | None
    created_at: datetime


class PaymentResultResponse(BaseModel):
    payment: PaymentResponse
    order_status: Literal["pending", "paid"]
    already_paid: bool = False
