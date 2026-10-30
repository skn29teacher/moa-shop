from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProductWriteRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default='', max_length=5000)
    price: int = Field(gt=0, le=999999999999, strict=True)
    stock: int = Field(ge=0, le=2147483647, strict=True)

    @field_validator('name', mode='before')
    @classmethod
    def strip_name(cls, value):
        return value.strip() if isinstance(value, str) else value


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
