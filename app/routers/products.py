from typing import Annotated
from uuid import UUID

from flask import Blueprint, request
from pydantic import Field

from app.core.http import json_response, validate_value
from app.db.connection import get_connection
from app.schemas.products import ProductListResponse, ProductResponse
from app.services import products as service


router = Blueprint("products", __name__, url_prefix="/api/products")


@router.get("")
def list_products():
    limit = validate_value(
        Annotated[int, Field(ge=1, le=100)],
        request.args.get("limit", "20"),
        "query.limit",
    )
    offset = validate_value(
        Annotated[int, Field(ge=0)],
        request.args.get("offset", "0"),
        "query.offset",
    )
    result = service.list_products(get_connection(), limit, offset)
    return json_response(result, ProductListResponse)


@router.get("/<product_id>")
def get_product(product_id: str):
    product_id = validate_value(UUID, product_id, "path.product_id")
    result = service.get_product(get_connection(), product_id)
    return json_response(result, ProductResponse)
