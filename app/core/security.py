from datetime import datetime, timedelta, timezone
from flask import Response
from app.core.config import Settings
from app.core.errors import HTTPException

AUTH_COOKIE_NAME = "shop_access_token"


def authentication_error() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail="로그인이 필요하거나 로그인 정보가 유효하지 않습니다.",
    )


def set_auth_cookie(response: Response, token: str, settings: Settings) -> None:
    seconds = settings.session_days * 86400
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        max_age=seconds,
        expires=datetime.now(timezone.utc) + timedelta(seconds=seconds),
        path="/",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )


def clear_auth_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=AUTH_COOKIE_NAME,
        path="/",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )
