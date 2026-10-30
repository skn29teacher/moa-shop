# PythonAnywhere 배포 과정

실제로 진행한 SQLite + Supabase Auth 배포 순서입니다. 계정명은 `kyuyounglee`, 앱 폴더는 `/home/kyuyounglee/moashop`, 가상환경은 `/home/kyuyounglee/.virtualenvs/moashop-sqlite`입니다. 다른 계정에서는 이 세 경로와 도메인을 함께 바꾸세요.

## 1. 구성 이해하기

PythonAnywhere 무료 계정에 Flask와 SQLite 파일을 두고 Supabase Auth만 HTTPS로 호출합니다. 이전 PostgreSQL 직접 연결에서 발생했던 5432 포트 연결은 사용하지 않습니다. `.supabase.co`는 PythonAnywhere 무료 계정의 HTTPS [허용 목록](https://www.pythonanywhere.com/whitelist/)에 포함돼 있습니다. 실제 프로젝트의 접근 가능 여부는 뒤의 `check-auth` 명령으로 확인합니다.

## 2. ZIP 파일 업로드

PythonAnywhere에 로그인하고 **Files** 탭에서 `/home/kyuyounglee/`로 이동합니다. **Upload a file**로 `moashop-sqlite-deploy.zip`을 업로드합니다.

ZIP은 프로젝트 루트의 `app/`, `templates/`, `static/`, `sql/schema.sql`, `sql/seed.sql`, `wsgi.py`, 의존성 파일 등을 포함해야 합니다. 실제 `.env`, SQLite 파일, `.venv`, `.git`, 캐시와 기존 ZIP은 제외합니다. 소스 업데이트용 ZIP으로 서버의 설정·운영 DB를 덮어쓰지 않도록 구성합니다.

## 3. Bash에서 압축 풀기

**Consoles → Bash**를 열어 실행합니다. 기존 파일과 같은 이름의 소스는 최신 코드로 교체됩니다.

```bash
cd /home/kyuyounglee
mkdir -p moashop
unzip -o moashop-sqlite-deploy.zip -d moashop
cd moashop
ls app/cli.py sql/schema.sql wsgi.py requirements.txt
python3 --version
```

이번 작업에서는 파일 4개와 `Python 3.13.1` 출력을 확인했습니다.

## 4. 가상환경과 패키지 준비

가상환경이 이미 있으면 생성 명령을 건너뛰고 활성화부터 실행합니다.

```bash
cd /home/kyuyounglee/moashop
python3.13 -m venv /home/kyuyounglee/.virtualenvs/moashop-sqlite
source /home/kyuyounglee/.virtualenvs/moashop-sqlite/bin/activate
python -m pip install -r requirements.txt
python -c "import sys, sqlite3, flask, pydantic, cryptography; print('Python:', sys.version.split()[0]); print('SQLite:', sqlite3.sqlite_version); print('패키지 확인 완료')"
```

이번 배포에서는 Python 3.13.1과 SQLite 3.37.2를 확인했습니다. 앱에서 `RETURNING` 구문을 사용하므로 SQLite 3.35 이상이 필요합니다. 이후 Bash 작업은 이 가상환경을 활성화한 상태로 진행합니다.

## 5. 배포 서버의 .env 작성

Files에서 `/home/kyuyounglee/moashop/.env`를 열어 저장합니다. 아래 `REPLACE_...` 값은 반드시 본인의 실제 값으로 바꿉니다. 기존 유효한 SECRET_KEY가 있으면 유지합니다.

```dotenv
APP_ORIGIN=https://kyuyounglee.pythonanywhere.com
DATABASE_PATH=/home/kyuyounglee/moashop/instance/shop.sqlite3
SUPABASE_URL=https://REPLACE_PROJECT_ID.supabase.co
SUPABASE_KEY=REPLACE_WITH_PUBLISHABLE_OR_ANON_KEY
SECRET_KEY=REPLACE_WITH_EXISTING_OR_RANDOM_SECRET
SESSION_DAYS=7
COOKIE_SECURE=true
```

SECRET_KEY가 없을 때만 생성한 값을 저장합니다. 32자 이상의 무작위 문자열이어야 합니다.

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

APP_ORIGIN에는 끝의 `/`를 붙이지 않습니다. COOKIE_SECURE는 HTTPS 배포에서 true여야 합니다. SUPABASE_KEY는 publishable 또는 legacy anon 키를 사용하며 Auth 관리자 키는 필요하지 않습니다. 과거 DATABASE_URL은 더 이상 사용하지 않습니다. `.env`는 서버 파일로 관리하고 채팅이나 저장소에 올리지 않습니다.

## 6. Supabase 이메일 리다이렉트 설정

Supabase Dashboard의 **Authentication → URL Configuration**에서 다음을 저장합니다.

**Site URL**

```text
https://kyuyounglee.pythonanywhere.com
```

**Redirect URLs**에 아래 주소를 각각 추가합니다. 루트 주소는 기존에 발급된 루트 콜백과의 호환을 위한 것이고, 새 코드의 가입 요청은 `/auth/confirm`을 지정합니다.

```text
https://kyuyounglee.pythonanywhere.com/
https://kyuyounglee.pythonanywhere.com/auth/confirm
http://127.0.0.1:8000/
http://127.0.0.1:8000/auth/confirm
```

앱은 `APP_ORIGIN + /auth/confirm`을 `redirect_to`로 보냅니다. Supabase가 인증한 뒤 이 주소로 돌아오면 앱은 인증 결과 fragment를 제거하고 `/#/login`을 표시합니다. 이메일 링크만으로 SQLite 앱 세션을 만들지는 않습니다.

Confirm sign up 이메일 템플릿을 직접 수정했다면 링크가 `{{ .ConfirmationURL }}`을 사용하는지 확인하세요. `http://localhost:3000` 또는 잘못된 SiteURL을 직접 연결하는 템플릿은 다시 점검해야 합니다. 인증 동작은 Supabase의 확인 링크가 수행해야 하므로 이메일 버튼을 단순 로그인 페이지 링크로 바꾸면 안 됩니다. [리다이렉트 설정](https://supabase.com/docs/guides/auth/redirect-urls), [이메일 템플릿 변수](https://supabase.com/docs/guides/auth/auth-email-templates).

이미 발송된 이메일의 주소는 설정 저장으로 수정되지 않습니다. 설정·코드 반영 후 새 가입 인증 메일을 발송해 확인합니다. Supabase Dashboard에서 확인 메일을 재발송할 수 있으면 사용하고, 앱에는 별도 재발송 API가 없으므로 테스트에서는 새 이메일로 가입할 수도 있습니다.

## 7. SQLite와 Auth 연결 확인

```bash
cd /home/kyuyounglee/moashop
source /home/kyuyounglee/.virtualenvs/moashop-sqlite/bin/activate
python -m flask --app wsgi:application init-db
python -m flask --app wsgi:application seed-demo
python -m flask --app wsgi:application check-auth
```

실제로 확인한 출력은 다음과 같습니다.

```text
SQLite 3.37.2: /home/kyuyounglee/moashop/instance/shop.sqlite3
DB 초기화 완료 (기존 데이터 유지).
샘플 상품 준비 완료 (동일 ID의 상품·재고 유지).
Supabase Auth HTTPS 연결 성공.
```

`init-db`는 새 DB와 스키마를 준비하거나 기존 지원 스키마를 확인합니다. `seed-demo`는 같은 ID의 상품을 건너뛰어 재고를 초기화하지 않습니다. `check-auth`는 Supabase `/auth/v1/settings`에 읽기 요청을 보내는 검사이며 실제 로그인·메일 전송 성공까지 검증하는 명령은 아닙니다.

## 8. Web 탭 설정

기존 앱을 선택합니다. 처음 만드는 경우 **Add a new web app → Manual configuration → Python 3.13**으로 만듭니다. Web 앱과 가상환경의 Python 버전이 같아야 합니다. [PythonAnywhere Flask 배포 안내](https://help.pythonanywhere.com/pages/Flask/).

| 항목 | 값 |
| --- | --- |
| Source code | `/home/kyuyounglee/moashop` |
| Working directory | `/home/kyuyounglee/moashop` |
| Virtualenv | `/home/kyuyounglee/.virtualenvs/moashop-sqlite` |
| Python version | 3.13 |

**WSGI configuration file** 링크를 열어 아래 내용을 저장합니다.

```python
import sys

project_home = "/home/kyuyounglee/moashop"
if project_home not in sys.path:
    sys.path.insert(0, project_home)

from wsgi import application
```

Flask 개발 서버를 실행하는 `flask run` 명령은 PythonAnywhere 배포에 사용하지 않습니다. Web의 WSGI가 앱을 실행합니다. Flask가 정적 파일도 제공하므로 별도 Static files 설정은 필수가 아닙니다. 추가하려면 URL `/static/`과 경로 `/home/kyuyounglee/moashop/static/`을 연결하고 instance 폴더는 공개하지 않습니다.

## 9. Reload와 동작 확인

Web 탭 상단의 **Reload**를 누르고 [사이트](https://kyuyounglee.pythonanywhere.com/)에 접속합니다. 샘플 상품 조회 → 가입 → 새 메일 인증 → 로그인 → 장바구니 → 주문 → 모의 결제를 확인합니다. 새 JS 파일을 반영한 뒤에는 브라우저를 강력 새로고침합니다.

SQLite 프로필은 서버에서 첫 로그인이 성공할 때 생성됩니다. 로컬 PC에서 지정한 관리자 역할은 서버에 자동 복사되지 않습니다. 서버에 먼저 로그인한 뒤 Bash에서 신뢰하는 Auth UUID로 부여합니다.

```bash
python -m flask --app wsgi:application set-role --auth-user-id '실제-Auth-UUID' --role admin
# 회수
python -m flask --app wsgi:application set-role --auth-user-id '실제-Auth-UUID' --role customer
```

## 10. 업데이트와 문제 해결

업데이트는 최신 소스 ZIP 업로드 → 압축 해제 → 같은 가상환경 활성화 → 필요시 의존성 설치 → Web Reload 순서로 진행합니다. `.env`, SECRET_KEY와 SQLite 파일은 유지합니다. SQLite 파일은 소스 배포 ZIP에 넣지 않습니다.

| 증상 | 확인할 내용 |
| --- | --- |
| 이메일 인증이 localhost:3000으로 이동 | Supabase Site URL, Redirect URLs, 이메일 템플릿, 새 메일인지 확인 |
| 인증 후 상품 화면이 표시됨 | 이전 app.js가 반영됐는지 확인; 새 auth-confirmation.js·템플릿·main.py 업로드 후 Reload/강력 새로고침 |
| `/auth/confirm`이 404 | 새 main.py가 배포됐는지, Reload했는지 확인 |
| `consumeAuthConfirmation is not defined` | auth-confirmation.js 업로드 및 템플릿의 스크립트 순서 확인 |
| `ModuleNotFoundError` | Web의 Virtualenv와 패키지를 설치한 가상환경이 같은지 확인 |
| SQLite 버전 오류 | Web와 가상환경의 Python 버전 및 SQLite 3.35 이상 여부 확인 |
| `unable to open database file` | DATABASE_PATH와 부모 폴더 쓰기 권한 확인 |
| `database is locked` | 오래 실행되는 DB 작업·복수 프로세스 쓰기 확인; 앱은 최대 15초 대기 후 오류 응답 가능 |
| 로그인/변경 요청 403 | APP_ORIGIN이 실제 HTTPS 도메인과 정확히 같은지 확인 |
| check-auth 실패 | SUPABASE_URL·키·HTTPS 접근과 Supabase 상태 확인 |
| 최신 코드인데 PostgreSQL 접속 오류 | Web Source/WSGI 경로가 예전 프로젝트를 가리키는지 확인 |

오류 확인은 Web의 Error log 마지막 traceback부터 시작합니다. 비밀키나 인증 토큰이 있는 URL 전체를 공유하지 않습니다. 운영 데이터 백업은 SQLite `backup` API를 사용하거나 쓰기를 멈춘 상태에서 수행합니다. SQLite는 PythonAnywhere의 네트워크 파일시스템에서 동시 접근 제약이 있으므로 현재 구성은 소규모 시연을 대상으로 합니다. [플랫폼의 SQLite 안내](https://help.pythonanywhere.com/pages/MySiteIsSlow/).
