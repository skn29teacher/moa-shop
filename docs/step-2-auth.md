> 이 문서는 이전 단계의 기록입니다. 현재 Supabase Auth 인증·서버 세션·권한·DB 전환은 [로컬 인증 테스트 안내](local-auth-testing.md)를 기준으로 확인하세요.

# STEP 2 — 기본 구조·DB 연결·인증 API

[README](../README.md) · [환경변수 예시](../.env.example) · [테이블 정의서](table-definitions.md)

## 1. 변경 파일

| 파일 | 역할 |
| --- | --- |
| app/main.py | Flask 앱 생성, DB 풀 연결, 정적 경로, 오류 응답 |
| app/core/config.py | 프로젝트 .env 로드·설정 검증 |
| app/core/security.py | Argon2 해시, JWT 발급·검증, HttpOnly 쿠키 |
| app/core/csrf.py | 변경 요청 출처 검증 |
| app/core/dependencies.py | DB·로그인 회원 조회, 탈퇴 계정 거부 |
| app/db/connection.py | Supabase PostgreSQL 연결 풀, 트랜잭션 반환 |
| app/db/users.py | 회원 조회·INSERT, SQL 매개변수 바인딩 |
| app/schemas/auth.py | 회원가입·로그인 Pydantic 입력 검증, 공개 응답 모델 |
| app/services/auth.py | 가입 저장·중복 처리, 비밀번호·탈퇴 여부 확인 |
| app/routers/auth.py | POST 회원가입·로그인·로그아웃 |
| app 및 하위 폴더의 __init__.py | Python 패키지 구성 |
| static/css/.gitkeep, static/js/.gitkeep, templates/.gitkeep | 화면 작업용 빈 폴더 유지 |
| requirements.txt | Python 라이브러리 버전 범위 |
| .env.example | 비밀값을 포함하지 않은 환경변수 예시 |
| .gitignore | 실제 .env, 가상환경, Python 캐시 제외 |
| README.md | 로컬 실행과 현재 구현 범위 |
| docs/step-2-auth.md | 이번 단계의 설정·확인 안내 |

SQL 테이블 변경은 없습니다. STEP 1의 users를 그대로 사용하며 Supabase Auth 가입 API는 사용하지 않습니다.

## 2. Supabase 연결 설정

1. STEP 1의 schema.sql이 오류 없이 실행되어 테이블 5개가 존재하는지 확인합니다. 이미 생성했다면 schema.sql을 다시 실행하지 않습니다.
2. Supabase 프로젝트의 Connect에서 PostgreSQL 연결 문자열(URI)을 복사합니다.
3. 네트워크가 IPv6를 지원하면 Direct connection을 사용할 수 있습니다. IPv4 환경에서는 Session pooler URI를 사용합니다. 호스트·사용자·포트는 화면의 값을 그대로 사용하며 임의로 조합하지 않습니다.
4. `.env.example`을 `.env`로 복사한 뒤 DATABASE_URL에 URI를 넣고 비밀번호 자리표시자를 실제 DB 비밀번호로 바꿉니다. 비밀번호 특수문자는 URI에 맞게 URL 인코딩합니다.
5. README의 비밀키 생성 명령을 직접 실행하고 출력값을 SECRET_KEY에 입력합니다.
6. 로컬에서는 APP_ORIGIN=http://127.0.0.1:8000, COOKIE_SECURE=false를 사용합니다.

이 단계는 SQL 트랜잭션을 위해 직접 PostgreSQL로 연결하므로 **DATABASE_URL이 필수**입니다. SUPABASE_URL·SUPABASE_KEY는 .env 관리 항목으로 준비했지만 STEP 2 코드에서 사용하지 않으며 빈 값으로 둬도 됩니다. anon 키로 테이블에 접근하지 않습니다.

연결 역할에는 public.users의 SELECT·INSERT 권한이 필요하며 RLS를 우회할 수 있는 서버 전용 역할을 사용합니다. 연결 비밀번호와 키는 브라우저에 보내지 않습니다.

서버 시작 때 연결 풀을 열어 접속을 확인합니다. 사용할 수 있는 연결이 없으면 시작을 중단합니다. SSL 연결을 사용하며, 스키마 자동 생성·마이그레이션·샘플 자동 INSERT는 수행하지 않습니다.

## 3. 실행 명령

`C:\AI4`에서 실행합니다. 코드·가상환경·.env는 `C:\AI4\Day12-Demo\project`에 둡니다. 이미 .env나 .venv가 있다면 해당 생성·복사 줄을 건너뛰세요.

```powershell
Set-Location 'C:\AI4'
python -m venv .\Day12-Demo\project\.venv
.\Day12-Demo\project\.venv\Scripts\python.exe -m pip install -r .\Day12-Demo\project\requirements.txt
Copy-Item -LiteralPath .\Day12-Demo\project\.env.example -Destination .\Day12-Demo\project\.env
.\Day12-Demo\project\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

`Day12-Demo\project\.env`를 저장한 뒤 `C:\AI4`에서 실행합니다.

```powershell
Set-Location 'C:\AI4\Day12-Demo\project'
.\.venv\Scripts\python.exe -m flask --app wsgi:application run --debug --no-reload --host 127.0.0.1 --port 8000
```

프로젝트 루트에서 실행하면 `.env`와 정적 파일은 프로젝트 절대 경로로 찾습니다.

브라우저에서 [http://127.0.0.1:8000/](http://127.0.0.1:8000/)을 엽니다. APP_ORIGIN이 127.0.0.1이면 localhost로 접속하지 않습니다. Flask는 자동 `/docs` API 문서를 제공하지 않으므로 아래 요청 예시를 API 클라이언트로 호출하거나 화면을 이용합니다.

## 4. API 확인 시나리오

아래 경로와 JSON 요청 예시를 API 클라이언트에서 호출합니다. 변경 요청은 같은 출처 검증을 위해 `Origin: http://127.0.0.1:8000` 헤더를 포함하고, 로그인 후에는 응답의 HttpOnly 쿠키를 유지해야 합니다.

### 회원가입

POST /api/auth/signup

```json
{
  "email": "buyer@example.com",
  "password": "ShopDemo2026!",
  "name": "김구매",
  "phone": "010-1234-5678",
  "address": "서울시 예시로 10"
}
```

201과 UUID·이메일·이름·연락처·주소·가입시각을 반환합니다. 비밀번호와 해시는 응답에 없습니다. Supabase Table Editor의 users에서 회원이 추가되고 password_hash가 `$argon2id$`로 시작하는지 직접 확인합니다.

같은 요청을 다시 보내면 409입니다. 이메일은 앞뒤 공백 제거·소문자로 정규화해 대소문자로 중복 가입하지 못하게 합니다.

### 로그인

POST /api/auth/login

```json
{
  "email": "buyer@example.com",
  "password": "ShopDemo2026!"
}
```

200과 사용자 정보를 반환하고 shop_access_token 쿠키를 설정합니다. 응답 JSON에 JWT를 노출하지 않습니다. 브라우저 개발자도구의 Application/Storage → Cookies에서 해당 호스트의 shop_access_token, HttpOnly, SameSite=Lax를 확인합니다. 로컬 HTTP에서는 Secure가 꺼져 있는 것이 정상입니다.

비밀번호만 다른 값으로 바꾸면 401입니다. 존재하지 않는 이메일과 탈퇴한 회원도 동일한 실패 메시지를 반환합니다. 실패한 로그인은 기존 쿠키를 새로 발급하거나 갱신하지 않습니다.

### 로그아웃

POST /api/auth/logout을 호출합니다. 본문 입력 없이 Execute를 누르면 204와 빈 응답을 반환하고 인증 쿠키를 제거합니다. 로그인하지 않은 상태에서 반복해도 204입니다.

### 입력값 검증

가입 비밀번호를 7자로 줄이거나 name을 공백만 입력하면 422입니다. 연락처·주소는 생략하거나 빈 문자열을 보내면 NULL로 저장합니다. 연락처는 숫자 7~15자리이며 +, 공백, 괄호, -를 함께 사용할 수 있습니다. 정의하지 않은 JSON 필드는 422로 거부합니다.

비밀번호는 가입 시 8~128자입니다. 해시하기 전 공백을 제거하거나 문자열을 임의로 바꾸지 않습니다. 실제 비밀번호를 오류 응답에 포함하지 않습니다.

## 5. 요청 → 처리 → 응답

1. 변경 요청의 Origin 또는 Referer를 APP_ORIGIN과 비교해 외부 사이트 요청을 403으로 차단합니다.
2. Pydantic이 이메일·비밀번호·이름·연락처 입력을 검증하고 필요한 값만 정규화합니다.
3. 가입은 Argon2 해시와 회원 정보를 저장해 커밋한 뒤 201, 로그인은 해시·탈퇴 여부를 검사한 뒤 200과 쿠키를 반환합니다.
4. 로그아웃은 같은 이름·경로의 쿠키를 만료시켜 204를 반환합니다.
5. 보호 API는 요청 쿠키의 JWT를 검증한 뒤 DB에서 회원 존재·탈퇴 여부를 확인하고 연결을 해제합니다.

## 6. 오류별 확인 방법

| 결과 | 확인할 내용 |
| --- | --- |
| 서버 시작 시 설정 검증 오류 | DATABASE_URL 자리표시자, SECRET_KEY 길이, APP_ORIGIN 형식 |
| DB 연결 시작 실패 | Supabase 프로젝트 상태, URI·비밀번호·사용자·포트, IPv4/IPv6 연결 방식 |
| 403 | 브라우저 주소와 APP_ORIGIN 일치 여부, Origin/Referer 헤더 |
| 409 | 정규화한 이메일로 이미 가입했는지 확인 |
| 422 | errors의 field·message 확인 |
| 401 | 이메일·비밀번호와 deleted_at 확인 |
| 503 | 실행 중 DB 연결을 사용할 수 없음, Supabase 연결 상태 확인 |

Origin 검증은 가입·로그인·로그아웃 모두 적용합니다. API 클라이언트로 호출할 경우 `Origin: http://127.0.0.1:8000`을 명시합니다. Origin과 Referer가 모두 없으면 403입니다.

에러를 공유할 때 응답 상태·detail 또는 서버의 마지막 오류를 알려주세요. .env, 실제 비밀번호, 쿠키/JWT, DB URI 전체는 보내지 마세요.

## 7. 사용자 확인 체크리스트

- [ ] `/`에서 쇼핑몰 화면이 열린다. O/X
- [ ] 회원가입 201, users에 새 회원이 보인다. O/X
- [ ] password_hash가 원문이 아닌 Argon2 해시다. O/X
- [ ] 같은 이메일 가입은 409다. O/X
- [ ] 잘못된 입력은 422이며 비밀번호 원문이 응답에 없다. O/X
- [ ] 올바른 로그인은 200이고 HttpOnly 쿠키가 생긴다. O/X
- [ ] 틀린 비밀번호 로그인은 401이다. O/X
- [ ] 로그아웃은 204이고 쿠키가 제거된다. O/X

## 8. 가정·검증 범위

- Python 3.11 이상, 신규 가상환경을 기준으로 작성했습니다. 의존성은 주 버전 범위로 지정했으며 설치·호환 실행은 하지 않았습니다.
- 비밀번호 해시는 bcrypt와 같은 목적의 검증된 방식인 Argon2id를 사용합니다.
- 직접 PostgreSQL 연결을 사용하며 Supabase Auth·브라우저의 Supabase 직접 호출은 사용하지 않습니다.
- 가입 후 자동 로그인하지 않고 로그인 API를 별도로 호출합니다.
- 로그아웃은 브라우저 쿠키 제거 방식이며, 복사된 JWT를 서버에서 즉시 폐기하지 않습니다. 만료는 기본 60분입니다.
- SQL·Python 코드 실행, 서버 시작, 설치·빌드·배포, 브라우저 조작, 자동 테스트는 수행하지 않았습니다. 사용자 실행 결과를 받은 뒤 필요한 파일만 수정합니다.

## 참고 문서

- [Flask 배포 문서](https://flask.palletsprojects.com/en/stable/deploying/)
- [Psycopg 연결 풀](https://www.psycopg.org/psycopg3/docs/advanced/pool.html)
- [Pydantic 설정 관리](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [Supabase PostgreSQL 연결](https://supabase.com/docs/guides/database/connecting-to-postgres)

확인 후 결과나 수정사항을 알려주세요. 다음 단계는 사용자 지시 후 진행합니다.
