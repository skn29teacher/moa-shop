# 쇼핑몰 MVP

**현재 인증: Supabase Auth + 서버 세션 + customer/admin 권한 관리. 배포 전 [로컬 실행·SQL 전환·테스트·피드백 안내](docs/local-auth-testing.md)를 먼저 확인하세요.**

현재 프로젝트는 Flask WSGI 웹 서버와 쇼핑몰 API·화면을 포함합니다. PythonAnywhere 배포 절차는 아래 안내를 참고하세요.

## 기술 구성

Python 3.11 이상, Flask, Pydantic, Supabase PostgreSQL을 사용합니다. Flask 개발 서버와 WSGI 진입 파일로 실행하며 Uvicorn은 사용하지 않습니다. 프론트엔드는 순수 HTML·CSS·JavaScript입니다. Node.js와 npm은 사용하지 않습니다.

## 폴더 구조

```text
project/
├─ app/
│  ├─ main.py                 # Flask 앱 생성, DB 풀, 정적 파일, 오류 처리
│  ├─ core/                   # 설정, Supabase Auth·쿠키, 권한 검사, CSRF
│  ├─ db/                     # 연결 풀과 매개변수 바인딩 SQL
│  ├─ routers/                # 인증·상품·장바구니·주문·결제 API
│  ├─ services/               # 인증·상품·장바구니·주문·결제 업무 처리
│  └─ schemas/                # 요청 검증·응답 필드
├─ static/css/               # STEP 5 예정
├─ static/js/                # STEP 5 예정
├─ templates/                # STEP 5 예정
├─ sql/schema.sql
├─ sql/auth-migration.sql
├─ sql/reset-shop-db.sql       # 쇼핑몰 테이블 초기화가 필요할 때만 사용
├─ sql/seed.sql
├─ docs/step-2-auth.md        # 설정·API 확인 시나리오
├─ docs/step-3-shopping.md    # 구매 API·재고·결제 확인 시나리오
├─ requirements.txt
├─ wsgi.py                    # PythonAnywhere WSGI 진입점
├─ .env.example
└─ README.md
```

## 로컬 실행 — 사용자가 직접 수행

PowerShell의 실행 위치는 `C:\AI4`입니다. 코드·가상환경·.env는 `C:\AI4\Day12-Demo\project`에 유지합니다.

```powershell
Set-Location 'C:\AI4'
python -m venv .\Day12-Demo\project\.venv
.\Day12-Demo\project\.venv\Scripts\python.exe -m pip install -r .\Day12-Demo\project\requirements.txt
Copy-Item -LiteralPath .\Day12-Demo\project\.env.example -Destination .\Day12-Demo\project\.env
.\Day12-Demo\project\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

가상환경이 이미 있으면 생성 명령을 건너뛰고, `.env`가 이미 있으면 복사 명령을 건너뛰세요. 마지막 명령의 결과를 `Day12-Demo\project\.env`의 SECRET_KEY로 저장하고 DATABASE_URL, SUPABASE_URL, SUPABASE_KEY를 같은 Supabase 테스트 프로젝트의 값으로 변경합니다. SQL 마이그레이션과 정확한 실행 순서는 [로컬 인증 테스트 안내](docs/local-auth-testing.md)를 참고하세요.

설정을 저장한 다음 `C:\AI4`에서 Flask 개발 서버를 시작합니다. `.env`와 정적 파일은 프로젝트 절대 경로로 찾습니다.

```powershell
Set-Location 'C:\AI4\Day12-Demo\project'
.\.venv\Scripts\python.exe -m flask --app wsgi:application run --debug --no-reload --host 127.0.0.1 --port 8000
```

브라우저에서 [http://127.0.0.1:8000/](http://127.0.0.1:8000/)을 엽니다. Flask 앱은 자동 Swagger 문서를 제공하지 않습니다. 종료는 실행한 터미널에서 `Ctrl+C`입니다.

## 인증 방식

Supabase Auth가 회원가입·로그인·비밀번호 변경·토큰 갱신을 처리합니다. 브라우저에는 HttpOnly/SameSite=Lax 세션 쿠키를 전달하고, 서버 DB에는 쿠키 해시와 암호화한 Supabase 토큰을 저장합니다. 로그아웃 시 서버 세션을 즉시 삭제합니다. 비밀번호 변경·탈퇴 시 모든 앱 세션을 삭제합니다.

회원 가입·로그인·비밀번호 검증은 Supabase Auth의 auth.users가 처리합니다. public.users는 쇼핑몰 프로필·역할·탈퇴 상태와 주문 관계를 저장하며, Auth 가입 트리거가 신규 프로필을 만듭니다. 회원 데이터 이관은 필수가 아니지만, auth_user_id 컬럼과 트리거를 설치하는 DB 스키마 변경은 필요합니다. 기존 Auth 계정을 계속 사용할 때만 해당 프로필을 명시적으로 연결하세요.

새 DB는 schema.sql → auth-migration.sql → seed.sql 순서로 실행합니다. 기존 테이블의 쇼핑몰 데이터를 모두 지우고 다시 만들려면 Supabase Authentication의 테스트 사용자도 먼저 삭제한 뒤 reset-shop-db.sql → schema.sql → auth-migration.sql → seed.sql 순서로 실행합니다. reset-shop-db.sql은 모든 쇼핑몰 회원 프로필·상품·주문·결제·앱 세션을 삭제하며 되돌릴 수 없습니다. 기존 데이터를 보존할 때는 이 파일을 실행하지 말고 auth-migration.sql만 1회 실행하세요. 자세한 내용은 [상세 안내](docs/local-auth-testing.md)를 확인하세요.

## API

| 메서드 | 경로 | 성공 | 역할 |
| --- | --- | --- | --- |
| POST | /api/auth/signup | 202 | 가입 접수, 이메일 인증 안내, 자동 로그인 없음 |
| POST | /api/auth/login | 200 | 사용자 응답과 HttpOnly 쿠키 설정 |
| POST | /api/auth/logout | 204 | 서버 세션 폐기 및 인증 쿠키 제거 |
| POST | /api/admin/products | 201 | 관리자 상품 등록 |
| PUT | /api/admin/products/{product_id} | 200 | 관리자 상품·가격·재고 수정 |
| GET | /api/admin/orders | 200 | 관리자 전체 주문 조회(limit/offset) |
| GET | /api/products | 200 | 공개 상품 목록 |
| GET | /api/products/{product_id} | 200 | 공개 상품 상세 |
| GET | /api/cart | 200 | 본인 장바구니 |
| POST | /api/cart/items | 200 | 상품 담기·같은 상품 수량 더하기 |
| PATCH | /api/cart/items/{product_id} | 200 | 수량을 지정한 값으로 변경 |
| DELETE | /api/cart/items/{product_id} | 200 | 상품 삭제·갱신된 장바구니 반환 |
| POST | /api/orders | 201 | cart 또는 buy_now 주문 생성 |
| GET | /api/orders/{order_id} | 200 | 본인 주문 상세 |
| POST | /api/orders/{order_id}/payments | 200 / 409 | 모의 결제·재고 부족 실패 기록 |

현재 인증은 [로컬 인증 테스트 안내](docs/local-auth-testing.md), 구매 과정은 [STEP 3 안내](docs/step-3-shopping.md)를 확인하세요. API는 JSON 응답이며 비로그인은 보호 API에서 401을 반환합니다. 로그인 화면 이동은 STEP 6에서 연결합니다.

## PythonAnywhere 배포

1. PythonAnywhere의 **Web** 탭에서 Manual configuration으로 웹 앱을 만들고, 설치한 프로젝트와 같은 Python 버전을 선택합니다.
2. Bash 콘솔에서 저장소를 계정 홈에 복제하고 가상환경을 만든 뒤 의존성을 설치합니다.

```bash
cd ~
git clone <repository-url> moa-shop
python3.11 -m venv ~/.virtualenvs/moa-shop
source ~/.virtualenvs/moa-shop/bin/activate
pip install -r ~/moa-shop/requirements.txt
```

3. 프로젝트 루트에 `.env`를 만들고 실제 `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_KEY`(publishable/anon), 32자 이상의 무작위 `SECRET_KEY`, PythonAnywhere의 앱 도메인에 맞춘 `APP_ORIGIN`을 설정합니다. HTTPS이면 `COOKIE_SECURE=true`로 설정합니다. `.env`는 저장소에 커밋하지 마세요.
4. Web 탭에서 **Source code**와 **Working directory**를 `~/moa-shop`, **Virtualenv**를 `~/.virtualenvs/moa-shop`으로 지정합니다.
5. Web 탭의 **WSGI configuration file**에서 기본 코드를 아래처럼 바꿉니다. `<username>`은 실제 PythonAnywhere 계정명으로 바꿉니다.

```python
import sys

project_home = "/home/<username>/moa-shop"
if project_home not in sys.path:
    sys.path.insert(0, project_home)

from wsgi import application
```

6. (선택) Static files 항목에 URL `/static/`, 경로 `/home/<username>/moa-shop/static/`을 추가합니다. 저장소의 Flask 앱도 `/static`을 제공하므로 이 매핑 없이도 동작합니다.
7. Web 탭에서 **Reload**를 누르고 앱 도메인을 확인합니다. 시작에 실패하면 Error log와 Server log를 확인하세요. 서버 프로세스에서 `.env`를 읽고 DB 연결 풀을 열기 때문에 앱 도메인·DB 연결이 올바르게 설정되어야 합니다.

PythonAnywhere 계정 플랜과 DB 제공자의 네트워크 정책에 따라 Supabase PostgreSQL로 나가는 연결이 허용되어야 합니다. 배포 전에 해당 환경에서 `DATABASE_URL` 접속 가능 여부를 확인하세요. Swagger `/docs` 대신 앱 화면 또는 API 클라이언트로 API를 확인합니다.

## 다음 단계

테스트 방법은 [pytest 안내](tests/README.md)를 참고하세요.
"# moa-shop" 
