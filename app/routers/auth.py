from fastapi import APIRouter, Request, Response, status

from app.core.dependencies import DatabaseConnection
from app.core.security import clear_auth_cookie, create_access_token, set_auth_cookie
from app.schemas.auth import LoginRequest, LoginResponse, SignupRequest, UserResponse
from app.services import auth as auth_service


router = APIRouter(prefix="/api/auth", tags=["인증"])


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, connection: DatabaseConnection):
    """회원가입만 처리합니다. 가입 후 로그인 API를 호출하세요."""
    return auth_service.signup(connection, payload)


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    connection: DatabaseConnection,
):
    user = auth_service.login(connection, payload)
    settings = request.app.state.settings
    token = create_access_token(user["id"], settings)
    set_auth_cookie(response, token, settings)
    # JWT는 본문에 넣지 않고 HttpOnly 쿠키로만 전달합니다.
    return LoginResponse(user=UserResponse.model_validate(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def logout(request: Request):
    """미로그인 상태에서도 같은 결과를 반환하고 브라우저 인증 쿠키를 제거합니다."""
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_auth_cookie(response, request.app.state.settings)
    return response
