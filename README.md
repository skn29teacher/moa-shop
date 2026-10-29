# 쇼핑몰 MVP

현재 완료 범위는 **STEP 1 설계 + STEP 2 인증 API + STEP 3 상품·장바구니·주문·모의 결제 API 작성**입니다. 실행 확인은 사용자가 진행합니다. 회원정보·구매내역 API, 화면, Render 설정은 후속 단계에서 추가합니다.

## 기술 구성

Python 3.11 이상, FastAPI, Uvicorn, Supabase PostgreSQL을 사용합니다. 프론트엔드 폴더는 순수 HTML·CSS·JavaScript용입니다. Node.js와 npm은 사용하지 않습니다.

## 폴더 구조

```text
project/
├─ app/
│  ├─ main.py                 # 앱 시작·종료, 정적 파일, 오류 처리
│  ├─ core/                   # 설정, 비밀번호·JWT·쿠키, 인증 의존성, CSRF
│  ├─ db/                     # 연결 풀과 매개변수 바인딩 SQL
│  ├─ routers/                # 인증·상품·장바구니·주문·결제 API
│  ├─ services/               # 인증·상품·장바구니·주문·결제 업무 처리
│  └─ schemas/                # 요청 검증·응답 필드
├─ static/css/               # STEP 5 예정
├─ static/js/                # STEP 5 예정
├─ templates/                # STEP 5 예정
├─ sql/schema.sql
├─ sql/seed.sql
├─ docs/step-2-auth.md        # 설정·Swagger 확인 시나리오
├─ docs/step-3-shopping.md    # 구매 API·재고·결제 확인 시나리오
├─ requirements.txt
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

가상환경이 이미 있으면 생성 명령을 건너뛰고, `.env`가 이미 있으면 복사 명령을 건너뛰세요. 마지막 명령의 결과를 `Day12-Demo\project\.env`의 SECRET_KEY로 저장하고 DATABASE_URL을 실제 연결 문자열로 변경합니다. 자세한 설정은 [STEP 2 안내](docs/step-2-auth.md)를 참고하세요.

설정을 저장한 다음 `C:\AI4`에서 서버를 시작합니다. `--app-dir`로 app 패키지 위치를 지정하고 `--reload-dir`로 코드 변경 감시 범위를 지정합니다. .env와 정적 파일은 코드에서 프로젝트 절대 경로를 사용하므로 실행 폴더와 관계없이 찾습니다.

```powershell
Set-Location 'C:\AI4'
.\Day12-Demo\project\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir .\Day12-Demo\project --reload --reload-dir .\Day12-Demo\project\app --host 127.0.0.1 --port 8000
```

[Swagger](http://127.0.0.1:8000/docs)에서 확인합니다. 종료는 실행한 터미널에서 `Ctrl+C`입니다. 현재 `/`에는 화면을 추가하지 않아 404가 정상이며 `/docs`로 접속해야 합니다.

## 인증 방식

JWT를 HttpOnly 쿠키로 전달해 서버 세션 테이블 없이 인증을 처리합니다. 비밀번호는 Argon2로 해시합니다. 쿠키는 SameSite=Lax이며 HTTPS 배포 시 Secure=true를 사용합니다. 변경 요청은 APP_ORIGIN과 Origin 또는 Referer가 일치해야 합니다.

로그아웃은 현재 브라우저의 인증 쿠키를 제거합니다. 별도 서버 세션 저장소를 두지 않으므로 복사해 둔 JWT 자체를 즉시 폐기하는 기능은 없고, JWT 유효기간은 기본 60분입니다.

## API

| 메서드 | 경로 | 성공 | 역할 |
| --- | --- | --- | --- |
| POST | /api/auth/signup | 201 | 회원 생성, 자동 로그인 없음 |
| POST | /api/auth/login | 200 | 사용자 응답과 HttpOnly 쿠키 설정 |
| POST | /api/auth/logout | 204 | 인증 쿠키 제거, 응답 본문 없음 |
| GET | /api/products | 200 | 공개 상품 목록 |
| GET | /api/products/{product_id} | 200 | 공개 상품 상세 |
| GET | /api/cart | 200 | 본인 장바구니 |
| POST | /api/cart/items | 200 | 상품 담기·같은 상품 수량 더하기 |
| PATCH | /api/cart/items/{product_id} | 200 | 수량을 지정한 값으로 변경 |
| DELETE | /api/cart/items/{product_id} | 200 | 상품 삭제·갱신된 장바구니 반환 |
| POST | /api/orders | 201 | cart 또는 buy_now 주문 생성 |
| GET | /api/orders/{order_id} | 200 | 본인 주문 상세 |
| POST | /api/orders/{order_id}/payments | 200 / 409 | 모의 결제·재고 부족 실패 기록 |

인증은 [STEP 2 안내](docs/step-2-auth.md), 구매 과정은 [STEP 3 안내](docs/step-3-shopping.md)를 확인하세요. API는 JSON 응답이며 비로그인은 보호 API에서 401을 반환합니다. 로그인 화면 이동은 STEP 6에서 연결합니다.

## STEP 3 실행

기존 가상환경이 활성화된 `C:\AI4` 터미널에서 실행합니다. requirements.txt와 DB 테이블 변경이 없어 추가 설치나 schema.sql 재실행은 필요하지 않습니다.

```powershell
Set-Location 'C:\AI4'
python -m uvicorn app.main:app --app-dir .\Day12-Demo\project --reload --reload-dir .\Day12-Demo\project\app --host 127.0.0.1 --port 8000
```

## 다음 단계

STEP 4 회원정보·구매내역 → STEP 5 화면 → STEP 6 로그인 복귀 → STEP 7 Render 배포 순서로 진행합니다. 각 단계는 사용자 지시 후 시작합니다.
"# moa-shop" 
