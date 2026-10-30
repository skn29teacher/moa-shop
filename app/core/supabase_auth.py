"""Request-local Supabase Auth REST client; never logs credentials or provider bodies."""
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from flask import current_app

from app.core.errors import HTTPException


class SupabaseAuth:
    def __init__(self, settings):
        self.url = settings.supabase_url.rstrip('/') + '/auth/v1'
        self.key = settings.supabase_key.get_secret_value()
        self.app_origin = settings.app_origin

    def call(self, method, path, body=None, token=None):
        headers = {'apikey': self.key, 'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        data = json.dumps(body).encode() if body is not None else None
        req = Request(self.url + path, data=data, headers=headers, method=method)
        try:
            with urlopen(req, timeout=10) as response:
                raw = response.read()
                return json.loads(raw) if raw else {}
        except HTTPError as exc:
            if exc.code == 429:
                raise HTTPException(status_code=429, detail='요청이 많습니다. 잠시 후 다시 시도하세요.') from None
            if exc.code >= 500:
                raise HTTPException(status_code=503, detail='인증 서비스를 사용할 수 없습니다.') from None
            if exc.code in (401, 403) or path.startswith('/token'):
                raise HTTPException(status_code=401, detail='이메일 또는 비밀번호가 올바르지 않거나 이메일 인증이 필요합니다.') from None
            raise HTTPException(status_code=400, detail='인증 요청을 처리하지 못했습니다. 입력값과 이메일 인증 상태를 확인하세요.') from None
        except (URLError, TimeoutError, OSError, ValueError):
            raise HTTPException(status_code=503, detail='인증 서비스를 사용할 수 없습니다.') from None

    def signup(self, payload):
        redirect = urlencode({'redirect_to': self.app_origin + '/auth/confirm'})
        return self.call('POST', '/signup?' + redirect, {
            'email': str(payload.email), 'password': payload.password.get_secret_value(),
            'data': payload.model_dump(exclude={'email', 'password'}),
        })

    def login(self, email, password):
        return self.call('POST', '/token?grant_type=password', {'email': email, 'password': password})

    def refresh(self, token):
        return self.call('POST', '/token?grant_type=refresh_token', {'refresh_token': token})

    def user(self, token):
        return self.call('GET', '/user', token=token)

    def logout(self, token):
        return self.call('POST', '/logout?scope=local', token=token)

    def password(self, token, password):
        return self.call('PUT', '/user', {'password': password}, token=token)


def provider():
    factory = current_app.config.get('auth_provider_factory', SupabaseAuth)
    return factory(current_app.config['settings'])
