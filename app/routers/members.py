from fastapi import APIRouter, Request, Response, status

from app.core.dependencies import CurrentUser, DatabaseConnection
from app.core.security import clear_auth_cookie
from app.schemas.auth import UserResponse
from app.schemas.members import PasswordChangeRequest, ProfileUpdateRequest
from app.schemas.orders import OrderResponse
from app.services import members as service


router = APIRouter(prefix="/api/members/me", tags=["회원정보·구매내역"])


@router.get("", response_model=UserResponse)
def get_profile(user: CurrentUser):
    return service.get_profile(user)


@router.patch("", response_model=UserResponse)
def update_profile(
    payload: ProfileUpdateRequest,
    user: CurrentUser,
    connection: DatabaseConnection,
):
    return service.update_profile(connection, user["id"], payload)


@router.put("/password", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def change_password(
    payload: PasswordChangeRequest,
    user: CurrentUser,
    connection: DatabaseConnection,
):
    service.change_password(connection, user["id"], payload)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_member(
    request: Request,
    user: CurrentUser,
    connection: DatabaseConnection,
):
    service.delete_member(connection, user["id"])
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_auth_cookie(response, request.app.state.settings)
    return response


@router.get("/orders", response_model=list[OrderResponse])
def list_purchase_history(user: CurrentUser, connection: DatabaseConnection):
    return service.list_purchase_history(connection, user["id"])
