import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    email: EmailStr = Field(max_length=254)
    password: SecretStr = Field(min_length=1, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        return value.strip().lower() if isinstance(value, str) else value


class SignupRequest(LoginRequest):
    password: SecretStr = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=30)
    address: str | None = Field(default=None, max_length=500)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("phone", "address", mode="before")
    @classmethod
    def normalize_optional_text(cls, value):
        if isinstance(value, str):
            return value.strip() or None
        return value

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is not None:
            digit_count = len(re.sub(r"\D", "", value))
            if not re.fullmatch(r"\+?[0-9 ()-]+", value) or not 7 <= digit_count <= 15:
                raise ValueError("연락처는 숫자 7~15자리와 +, 공백, 괄호, -만 사용하세요.")
        return value


class UserResponse(BaseModel):
    # password_hash나 deleted_at은 응답으로 내보내지 않습니다.
    id: UUID
    email: EmailStr
    name: str
    phone: str | None
    address: str | None
    created_at: datetime


class LoginResponse(BaseModel):
    message: str = "로그인되었습니다."
    user: UserResponse
