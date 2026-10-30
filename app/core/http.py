from typing import Any

from flask import jsonify, request
from pydantic import TypeAdapter, ValidationError
from werkzeug.exceptions import BadRequest

from app.core.errors import RequestValidationError


def _validation_errors(exc: ValidationError, source: str) -> list[dict]:
    return [
        {
            "field": [*source.split("."), *error["loc"]],
            "message": error["msg"],
            "type": error["type"],
        }
        for error in exc.errors(include_input=False)
    ]


def validate_model(model: Any, value: Any, source: str = "body") -> Any:
    try:
        return TypeAdapter(model).validate_python(value)
    except ValidationError as exc:
        raise RequestValidationError(_validation_errors(exc, source)) from None


def validate_value(value_type: Any, value: Any, source: str) -> Any:
    try:
        return TypeAdapter(value_type).validate_python(value)
    except ValidationError as exc:
        raise RequestValidationError(_validation_errors(exc, source)) from None


def request_body(model: Any) -> Any:
    if not request.is_json:
        return validate_model(model, None)
    try:
        value = request.get_json()
    except BadRequest:
        raise RequestValidationError(
            [{"field": ["body"], "message": "JSON 형식이 올바르지 않습니다.", "type": "json_invalid"}]
        ) from None
    return validate_model(model, value)


def json_response(value: Any, model: Any = None, status_code: int = 200):
    if model is not None:
        adapter = TypeAdapter(model)
        value = adapter.dump_python(adapter.validate_python(value), mode="json")
    return jsonify(value), status_code
