from flask import Blueprint, current_app
from flask import Response

from app.core.http import json_response, request_body
from app.core.security import clear_auth_cookie, set_auth_cookie
from app.db.connection import get_connection
from app.schemas.auth import LoginRequest, LoginResponse, SignupRequest, UserResponse
from app.services import auth as auth_service
from app.services import sessions


router = Blueprint("auth", __name__, url_prefix="/api/auth")


@router.post("/signup")
def signup():
    """회원가입만 처리합니다. 가입 후 로그인 API를 호출하세요."""
    payload = request_body(SignupRequest)
    return auth_service.signup(get_connection(), payload), 202


@router.post("/login")
def login():
    payload = request_body(LoginRequest)
    user, token = auth_service.login(get_connection(), payload)
    settings = current_app.config["settings"]
    response, status_code = json_response(
        LoginResponse(user=UserResponse.model_validate(user)), LoginResponse
    )
    set_auth_cookie(response, token, settings)
    return response, status_code


@router.post("/logout")
def logout():
    sessions.end(get_connection())
    response = Response(status=204)
    clear_auth_cookie(response, current_app.config["settings"])
    return response
