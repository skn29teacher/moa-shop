from app.core.errors import HTTPException
from app.services.sessions import current


def get_current_user() -> dict:
    return current()


def require_admin() -> dict:
    user = get_current_user()
    # DB role is reloaded on every request; never trust user metadata for authorization.
    if user['role'] != 'admin':
        raise HTTPException(status_code=403, detail='관리자 권한이 필요합니다.')
    return user
