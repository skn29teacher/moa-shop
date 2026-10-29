from fastapi import HTTPException, status
from psycopg import Connection
from psycopg.errors import UniqueViolation

from app.core.security import dummy_password_hash, hash_password, verify_password
from app.db.users import find_user_by_email, insert_user
from app.schemas.auth import LoginRequest, SignupRequest


def signup(connection: Connection, payload: SignupRequest) -> dict:
    try:
        # UNIQUE 제약으로 동시 회원가입에서도 이메일 중복을 차단합니다.
        # 응답을 만들기 전에 커밋까지 완료해 저장 실패를 성공으로 응답하지 않습니다.
        with connection.transaction():
            return insert_user(
                connection,
                email=str(payload.email),
                password_hash=hash_password(payload.password.get_secret_value()),
                name=payload.name,
                phone=payload.phone,
                address=payload.address,
            )
    except UniqueViolation:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 사용 중인 이메일입니다.",
        ) from None


def login(connection: Connection, payload: LoginRequest) -> dict:
    user = find_user_by_email(connection, str(payload.email))
    candidate_hash = user["password_hash"] if user else dummy_password_hash
    valid_password = verify_password(payload.password.get_secret_value(), candidate_hash)
    # 이메일 존재 여부와 탈퇴 여부를 로그인 실패 메시지로 구분하지 않습니다.
    if not user or not valid_password or user["deleted_at"] is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 올바르지 않습니다.",
        )
    return user
