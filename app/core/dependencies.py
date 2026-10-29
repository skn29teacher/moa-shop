from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import APIKeyCookie
from psycopg import Connection

from app.core.security import AUTH_COOKIE_NAME, authentication_error, decode_user_id
from app.db.connection import get_connection
from app.db.users import find_user_by_id


auth_cookie = APIKeyCookie(name=AUTH_COOKIE_NAME, auto_error=False)
DatabaseConnection = Annotated[Connection, Depends(get_connection)]


def get_current_user(
    request: Request,
    connection: DatabaseConnection,
    token: Annotated[str | None, Depends(auth_cookie)],
) -> dict:
    if not token:
        raise authentication_error()
    user_id = decode_user_id(token, request.app.state.settings)
    user = find_user_by_id(connection, user_id)
    # JWT가 유효해도 탈퇴한 회원은 모든 보호 API에서 거부합니다.
    if not user or user["deleted_at"] is not None:
        raise authentication_error()
    return user


CurrentUser = Annotated[dict, Depends(get_current_user)]
