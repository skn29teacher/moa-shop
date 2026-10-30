from flask import Blueprint, Response, current_app

from app.core.dependencies import get_current_user
from app.core.http import json_response, request_body
from app.core.security import clear_auth_cookie
from app.db.connection import get_connection
from app.schemas.auth import UserResponse
from app.schemas.members import PasswordChangeRequest, ProfileUpdateRequest
from app.schemas.orders import OrderResponse
from app.services import members as service


router = Blueprint("members", __name__, url_prefix="/api/members/me")


@router.get("")
def get_profile():
    user = get_current_user()
    return json_response(service.get_profile(user), UserResponse)


@router.patch("")
def update_profile():
    user = get_current_user()
    payload = request_body(ProfileUpdateRequest)
    result = service.update_profile(get_connection(), user["id"], payload)
    return json_response(result, UserResponse)


@router.put("/password")
def change_password():
    user = get_current_user()
    payload = request_body(PasswordChangeRequest)
    service.change_password(get_connection(), user["id"], payload)
    response = Response(status=204)
    clear_auth_cookie(response, current_app.config["settings"])
    return response


@router.delete("")
def delete_member():
    user = get_current_user()
    service.delete_member(get_connection(), user["id"])
    response = Response(status=204)
    clear_auth_cookie(response, current_app.config["settings"])
    return response


@router.get("/orders")
def list_purchase_history():
    user = get_current_user()
    result = service.list_purchase_history(get_connection(), user["id"])
    return json_response(result, list[OrderResponse])
