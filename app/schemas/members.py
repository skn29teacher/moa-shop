import re

from pydantic import Field, SecretStr, field_validator, model_validator

from app.schemas.orders import RequestModel


class ProfileUpdateRequest(RequestModel):
    """회원이 수정할 프로필 필드만 받으며, 빠진 필드는 그대로 둡니다."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
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
            digits = len(re.sub(r"\D", "", value))
            if not re.fullmatch(r"\+?[0-9 ()-]+", value) or not 7 <= digits <= 15:
                raise ValueError("연락처는 숫자 7~15자리와 +, 공백, 괄호, -만 사용하세요.")
        return value

    @model_validator(mode="after")
    def require_at_least_one_field(self):
        if not self.model_fields_set:
            raise ValueError("수정할 항목을 하나 이상 입력하세요.")
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("이름은 비워둘 수 없습니다.")
        return self


class PasswordChangeRequest(RequestModel):
    current_password: SecretStr = Field(min_length=1, max_length=128)
    new_password: SecretStr = Field(min_length=8, max_length=128)
