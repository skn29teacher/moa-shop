from app.core.errors import HTTPException
from app.core.supabase_auth import provider
from app.db import users
from app.services import sessions


def signup(connection, payload):
    result = provider().signup(payload)
    if result.get('access_token'):
        provider().logout(result['access_token'])
    return {'message': '가입 요청을 접수했습니다. 이메일 인증이 필요한 경우 메일의 인증 링크를 누른 뒤 로그인하세요.'}


def login(connection, payload):
    result = provider().login(str(payload.email), payload.password.get_secret_value())
    try:
        user = users.ensure_auth_profile(connection, result['user'])
    except Exception:
        try:
            provider().logout(result['access_token'])
        except HTTPException:
            pass
        raise
    if user['deleted_at'] is not None:
        provider().logout(result['access_token'])
        raise HTTPException(status_code=401, detail='사용 가능한 쇼핑몰 회원 정보가 없습니다.')
    sessions.end(connection)
    return user, sessions.start(connection, user, result)
