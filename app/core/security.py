from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from fastapi import HTTPException, Response, status
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

from app.core.config import Settings


AUTH_COOKIE_NAME = "shop_access_token"
JWT_ALGORITHM = "HS256"
JWT_ISSUER = "shopping-mvp"
JWT_AUDIENCE = "shopping-browser"
password_hasher = PasswordHash.recommended()
# 존재하지 않는 이메일도 해시 검증을 수행해 응답 시간 차이를 줄입니다.
dummy_password_hash = password_hasher.hash("dummy-password-not-an-account")


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password, password_hash)
    except (ValueError, UnknownHashError):
        return False


def authentication_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="로그인이 필요하거나 로그인 정보가 유효하지 않습니다.",
    )


def create_access_token(user_id: UUID, settings: Settings) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user_id),
            "iat": now,
            "nbf": now,
            "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
            "iss": JWT_ISSUER,
            "aud": JWT_AUDIENCE,
        },
        settings.secret_key.get_secret_value(),
        algorithm=JWT_ALGORITHM,
    )


def decode_user_id(token: str, settings: Settings) -> UUID:
    try:
        claims = jwt.decode(
            token,
            settings.secret_key.get_secret_value(),
            algorithms=[JWT_ALGORITHM],
            audience=JWT_AUDIENCE,
            issuer=JWT_ISSUER,
            options={"require": ["sub", "iat", "nbf", "exp", "iss", "aud"]},
        )
        return UUID(claims["sub"])
    except (jwt.InvalidTokenError, ValueError, TypeError, KeyError):
        raise authentication_error() from None


def set_auth_cookie(response: Response, token: str, settings: Settings) -> None:
    seconds = settings.access_token_expire_minutes * 60
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
