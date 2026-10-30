# 로컬 실행과 테스트

Windows PowerShell 기준입니다. 현재 프로젝트 위치는 `C:\AI4\Day12-Demo\project`이며 Python 3.11 이상, SQLite 3.35 이상이 필요합니다. SQLite는 Python 내장 모듈을 사용합니다.

## 1. 가상환경과 의존성

```powershell
Set-Location 'C:\AI4\Day12-Demo\project'
if (-not (Test-Path -LiteralPath '.\.venv\Scripts\python.exe')) {
    python -m venv .venv
}
.\.venv\Scripts\python.exe -m pip install -r requirements-test.txt
if (-not (Test-Path -LiteralPath '.\.env')) {
    Copy-Item -LiteralPath '.\.env.example' -Destination '.\.env'
}
.\.venv\Scripts\python.exe -c "import sqlite3; print(sqlite3.sqlite_version)"
```

## 2. 로컬 설정과 Supabase 주소

기존 실제 Supabase URL·키와 유효한 SECRET_KEY를 유지하면서 `.env`를 설정합니다. 아래 REPLACE 값은 실제 값으로 교체합니다.

```dotenv
APP_ORIGIN=http://127.0.0.1:8000
DATABASE_PATH=instance/shop.sqlite3
SUPABASE_URL=https://REPLACE_PROJECT_ID.supabase.co
SUPABASE_KEY=REPLACE_WITH_PUBLISHABLE_OR_ANON_KEY
SECRET_KEY=REPLACE_WITH_EXISTING_OR_RANDOM_SECRET
SESSION_DAYS=7
COOKIE_SECURE=false
```

키가 없을 때 생성합니다.

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

Supabase Authentication → URL Configuration의 Redirect URLs에는 `http://127.0.0.1:8000/auth/confirm`과 `http://127.0.0.1:8000/`를 추가합니다. Site URL은 운영 배포 주소로 유지해도 되며 로컬 앱은 APP_ORIGIN을 기준으로 가입 메일의 redirect_to를 지정합니다. 이메일 인증을 켠 경우 새 인증 메일로 확인합니다.

APP_ORIGIN과 브라우저 접속 주소는 같아야 합니다. `localhost`와 `127.0.0.1`은 다른 출처이므로 섞지 않습니다. `.env`를 바꾸면 실행 중인 서버를 재시작합니다. DATABASE_PATH의 상대경로 기준은 프로젝트 폴더이며, 기본 로컬 DB는 `project/instance/shop.sqlite3`입니다.

## 3. DB 준비와 서버 실행

```powershell
.\.venv\Scripts\python.exe -m flask --app wsgi:application init-db
.\.venv\Scripts\python.exe -m flask --app wsgi:application seed-demo
.\.venv\Scripts\python.exe -m flask --app wsgi:application check-auth
.\.venv\Scripts\python.exe -m flask --app wsgi:application run --debug --no-reload --host 127.0.0.1 --port 8000
```

[http://127.0.0.1:8000/](http://127.0.0.1:8000/)에 접속합니다. 종료는 Ctrl+C입니다. init-db와 seed-demo를 다시 실행해도 기존 지원 스키마와 같은 ID의 상품·판매 후 재고를 초기화하지 않습니다. check-auth는 실제 네트워크를 사용하는 읽기 검사이며, 계정을 만들거나 로그인하지 않습니다.

## 4. 자동 테스트

```powershell
Set-Location 'C:\AI4\Day12-Demo\project'
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests/test_sqlite_integration.py -q -p no:cacheprovider
# Node.js가 설치돼 있다면 이메일 콜백의 실제 JS 동작도 검사
node --test tests/auth-confirmation.test.cjs
node --check static/js/auth-confirmation.js
node --check static/js/app.js
```

Python 자동 테스트는 실제 `.env`나 운영 DB를 사용하지 않습니다. 외부 Auth HTTPS 경계를 대역으로 교체하고 SQLite 통합 테스트는 매번 임시 파일에서 실제 SQL을 실행합니다. Node.js는 JS 회귀 테스트에만 필요하고 Flask 앱 실행에는 필요하지 않습니다.

| 영역 | 확인 사항 |
| --- | --- |
| 입력·권한 | 요청 필드 검증, role 주입 차단, 일반 회원의 관리자 접근 거부, 타인 주문 접근 거부 |
| SQLite | 첫 로그인 프로필 생성, 외래키·UNIQUE, 영속성, 재고 차감과 결제 기록의 롤백 |
| 동시 요청 | 같은 계정 첫 로그인, 마지막 상품 구매, 같은 주문 중복 결제, 토큰 갱신 직렬화 |
| 세션 | 쿠키 위조·만료·로그아웃 후 재사용 차단, 암호화, 비밀번호 변경 후 모든 앱 세션 폐기 |
| 이메일 콜백 | 성공·실패·결과 없는 콜백, 파라미터 순서, 예전 루트 콜백, 토큰 제거와 로그인 화면 이동 |

실제 이메일 발송, 원격 Supabase 정책과 운영 브라우저 화면은 테스트 대역으로 검증하지 않으므로 다음 수동 검사를 함께 수행합니다.

2026-10-30 기준 Python 회귀 테스트 **137개**, 이메일 콜백 JavaScript 테스트 **5개**를 통과했습니다. 실제 Supabase 설정 변경과 새 메일의 리다이렉트는 운영 환경에서 별도로 확인해야 합니다.

## 5. 브라우저에서 확인하기

회원 A·B와 관리자 C를 서로 다른 브라우저 프로필 또는 시크릿 창으로 사용합니다.

| 순서 | 실행 | 기대 결과 |
| --- | --- | --- |
| 1 | 비회원으로 상품·장바구니 열기 | 상품 공개, 장바구니는 로그인 안내 |
| 2 | 가입 후 새 이메일의 Confirm email 클릭 | 해당 환경 `/auth/confirm` 도착 후 `/#/login`, URL의 토큰 제거 |
| 3 | 이메일·비밀번호 로그인 | 첫 성공 시 SQLite 프로필 생성; 기존 Auth 계정도 가능 |
| 4 | 이름·주소 수정 후 재로그인 | 로컬 수정 내용 유지 |
| 5 | 상품 담기·수량 변경·주문·모의 결제 | 총액·재고 정상; 성공 결제 재요청 시 추가 차감 없음 |
| 6 | B로 A의 주문 상세·결제 요청 | 404 |
| 7 | 일반 회원으로 관리자 화면·API 호출 | 403 |
| 8 | CLI로 C에게 admin 부여 후 관리자 화면 열기 | 상품 등록·수정과 전체 주문 조회 가능 |
| 9 | C를 customer로 변경 후 같은 세션으로 재요청 | 관리자 API 403 |
| 10 | 쿠키 기록 후 로그아웃, 기록한 쿠키로 재접근 | 보호 API 401 |
| 11 | 같은 계정 두 브라우저 로그인 후 비밀번호 변경 | 모두 다시 로그인 필요 |
| 12 | 탈퇴 후 같은 Auth 계정으로 로그인 | 차단; 기존 주문 보존 |
| 13 | 서버 재시작 후 같은 DB 사용 | 기존 데이터 유지 |

관리자 지정과 회수는 로컬 서버에서도 실제 Auth UUID를 사용합니다.

```powershell
.\.venv\Scripts\python.exe -m flask --app wsgi:application set-role --auth-user-id '실제-Auth-UUID' --role admin
.\.venv\Scripts\python.exe -m flask --app wsgi:application set-role --auth-user-id '실제-Auth-UUID' --role customer
```

## 6. 피드백 전달

```text
환경: 로컬 / PythonAnywhere
사용자 역할: 비회원 / customer / admin
실행한 명령 또는 화면:
재현 순서:
기대 결과:
실제 결과와 오류 메시지/HTTP 상태:
원하는 개선:
```

비밀번호·토큰·인증 메일 URL 전체·SECRET_KEY·DB 파일은 피드백에 넣지 않습니다. 이메일 리다이렉트 문제는 도착한 URL의 도메인과 경로만 알려주면 됩니다. 배포에서 설정할 항목과 오류별 확인 순서는 [DEPLOYMENT.md](DEPLOYMENT.md)에 정리했습니다.
