# Supabase Auth 전환 · 로컬 실행 · 피드백 안내

이 문서는 현재 인증 구현의 기준입니다. 이전 STEP 2의 자체 JWT·Argon2 로그인 설명은 과거 구현입니다. 배포 전에 아래 순서로 **별도 Supabase 테스트 프로젝트 + 로컬 Flask**에서 확인하세요. 자동 테스트는 외부 서비스 없이도 실행할 수 있습니다.

## 1. 변경된 인증과 권한

- 회원가입·이메일 인증·로그인·비밀번호 변경·토큰 갱신은 Supabase Auth가 처리합니다. 인증 계정과 비밀번호의 기준 테이블은 `auth.users`이며, 앱은 `public.users.password_hash`를 읽거나 자체 JWT를 발급하지 않습니다.
- `public.users`는 쇼핑몰 프로필·역할·탈퇴 상태와 주문의 회원 FK를 저장합니다. 현재 앱에서 필요하므로 제거할 수 없습니다. `auth_user_id`로 `auth.users.id`와 연결하며 주문 FK는 `public.users.id`를 사용합니다.
- `auth_sessions`는 Supabase의 인증 테이블이 아니라 브라우저 세션 쿠키와 암호화한 Supabase 토큰을 보관하는 앱의 서버 세션 테이블입니다.
- 브라우저에는 무작위 HttpOnly/SameSite=Lax 쿠키만 저장합니다. DB에는 쿠키의 SHA-256 해시와 SECRET_KEY로 암호화한 Supabase access/refresh token을 보관합니다. JSON 응답과 localStorage에는 토큰을 저장하지 않습니다.
- 보호 API는 서버 세션, Supabase `/user` 검증, 회원 활성 상태를 확인합니다. access token 만료가 가까우면 refresh token을 자동 교체합니다. DB 행 잠금으로 같은 세션의 동시 갱신을 직렬화합니다.
- 앱 세션 수명은 `SESSION_DAYS`(기본 7일)입니다. Supabase JWT 수명은 Supabase 설정을 따릅니다. 로그아웃은 해당 앱 세션을 즉시 삭제하고 Supabase의 해당 세션 로그아웃도 요청합니다. 인증 서비스 장애 중에도 앱 세션 삭제와 쿠키 제거는 수행합니다.
- 비밀번호 변경은 현재 비밀번호를 Supabase에서 재확인한 뒤 처리하고 **모든 앱 세션을 삭제**합니다. 다시 로그인해야 합니다. 탈퇴는 주문을 보존하며 모든 앱 세션을 삭제하고 이후 앱 로그인을 차단합니다.
- 역할은 매 요청 DB에서 읽습니다. 사용자 metadata나 요청의 `role` 값으로 관리자 권한을 부여하지 않습니다. 역할 변경 API는 제공하지 않으며 운영자가 SQL로 지정합니다.

| 기능 | 비회원 | 일반 회원(customer) | 관리자(admin) |
| --- | --- | --- | --- |
| 상품 목록·상세 | 가능 | 가능 | 가능 |
| 장바구니 조회·수정 | 401 | 본인만 | 본인만 |
| 주문 생성·상세·모의 결제·구매내역 | 401 | 본인만 | 본인만 |
| 프로필·비밀번호 변경·탈퇴 | 401 | 본인만 | 본인만 |
| 관리자 상품 등록·가격·재고 수정 | 401 | 403 | 가능 |
| 관리자 전체 고객 주문·배송정보 조회 | 401 | 403 | 가능 |
| 회원가입/프로필 수정으로 role 변경 | 불가 | 불가 | 불가 |

타인 주문은 소유권 검사로 404를 반환합니다. 주문·결제 금액과 재고는 서버에서 계산합니다. 관리자도 고객 결제 API로 타인의 주문을 결제할 수 없습니다. 이 프로젝트의 결제는 **모의 결제**입니다. 환불·배송 상태 변경·상품 삭제 기능은 현재 구현 범위에 없습니다.

DB Data API는 계속 닫아 둡니다. `anon`, `authenticated`, `PUBLIC`에 쇼핑몰 테이블 접근 권한을 부여하지 않으며 RLS도 활성화합니다. DB에 직접 연결하는 Flask 서버가 모든 권한·소유권 검사를 수행합니다. PostgreSQL 관리자 연결은 RLS를 우회할 수 있으므로 DATABASE_URL은 서버에만 보관합니다. 브라우저가 Supabase JWT로 테이블을 직접 수정하는 구조가 아닙니다.

## 2. Supabase 테스트 프로젝트 준비

1. 운영 DB와 분리한 Supabase 테스트 프로젝트를 준비합니다.
2. Authentication → Sign In / Providers에서 Email 로그인을 활성화합니다. Email confirmation을 사용하는 구성을 권장합니다. 로컬 실험용으로 끄는 경우 가입 직후 로그인할 수 있지만 앱은 자동 로그인하지 않습니다.
3. Authentication → URL Configuration의 Site URL을 `http://127.0.0.1:8000`으로 설정하고 Redirect URLs에 `http://127.0.0.1:8000/**`을 등록합니다. 가입 API도 `.env`의 `APP_ORIGIN`을 이메일 확인 redirect 주소로 명시하므로, 이전에 발송된 메일이 아닌 변경 후 새로 가입해 받은 메일로 확인하세요. 기존 메일은 발송 당시의 redirect 설정을 사용해 `localhost:3000` 등으로 이동할 수 있습니다. 앱은 성공한 인증 링크의 토큰 fragment를 주소창에서 제거하고 메인 상품 화면(`#/products`)으로 이동합니다. 인증 완료만으로 앱에 로그인되지는 않으므로 보호 기능은 로그인 후 이용할 수 있습니다. 인증 실패 링크는 로그인 화면으로 이동합니다.
4. Project URL, **publishable key 또는 legacy anon key**, Connect의 PostgreSQL 연결 URI를 준비합니다. IPv4 환경이면 Session pooler를 사용할 수 있습니다. Auth 관리자용 service_role/secret key는 필요하지 않습니다.
5. SQL Editor에서 원하는 DB 절차를 선택합니다. `schema.sql`은 기존 테이블이 있으면 실패하도록 설계되어 있으므로, 기존 테이블에 그대로 실행하지 마세요.

| DB 상태 | 실행 순서 |
| --- | --- |
| 쇼핑몰 테이블이 없는 새 테스트 DB | `sql/schema.sql` → `sql/auth-migration.sql` → `sql/seed.sql` |
| 기존 쇼핑몰 DB 복제본 | 백업 → `sql/auth-migration.sql` 1회 |
| 기존 테스트 데이터를 모두 지우고 재생성 | 아래의 전체 초기화 절차 |

`auth-migration.sql`은 **회원 레코드를 이관하지 않는 스키마 변경**입니다. `auth_user_id`, 역할 컬럼, 앱 세션 테이블 및 Auth 가입 트리거를 설치하며, 기존 쇼핑몰 회원·주문은 삭제하지 않습니다. 트랜잭션이므로 오류가 나면 전체가 롤백됩니다. 한 번만 실행하세요.

가입 요청은 Supabase Auth API를 통해 `auth.users`에 계정을 만듭니다. 마이그레이션의 트리거가 신규 Auth 계정의 프로필을 `public.users`에 만들고 두 UUID를 연결합니다. 로그인은 Supabase Auth에서 비밀번호를 검증한 다음 `public.users.auth_user_id`로 쇼핑몰 프로필·역할을 조회합니다. 따라서 로그의 `column "auth_user_id" does not exist`는 회원 데이터를 옮기지 않아서가 아니라, 앱이 연결한 DB에 이 스키마 변경이 적용되지 않았거나 다른 Supabase DB에 적용됐다는 뜻입니다.

### 기존 테스트 DB 전체 초기화

테스트 DB의 쇼핑몰 데이터가 모두 삭제되어도 괜찮을 때만 사용하세요. `sql/reset-shop-db.sql`은 `public.users`, 상품, 장바구니, 주문, 결제, 앱 세션과 가입 트리거를 삭제합니다. **Supabase가 관리하는 스키마와 `auth.users` 계정은 삭제하지 않습니다.** 기존 Auth 계정까지 초기화하려면 먼저 Supabase Dashboard → Authentication → Users에서 테스트 계정을 삭제하세요. 삭제하지 않은 Auth 계정은 새 프로필과 연결되지 않으므로 재가입해야 합니다.

Supabase Dashboard에서 현재 앱의 `DATABASE_URL`과 같은 프로젝트인지 확인한 뒤 SQL Editor에서 각 파일을 순서대로 실행합니다.

1. `sql/reset-shop-db.sql`
2. `sql/schema.sql`
3. `sql/auth-migration.sql`
4. `sql/seed.sql`

`reset-shop-db.sql`은 기존 쇼핑몰 데이터를 영구 삭제합니다. 운영 데이터가 있거나 대상 프로젝트가 확실하지 않으면 실행하지 말고, 새 Supabase 테스트 프로젝트를 만드세요. `DROP SCHEMA public CASCADE`나 `auth` 스키마 삭제는 Supabase 관리 객체까지 손상시킬 수 있으므로 사용하지 마세요.

적용 여부는 Supabase SQL Editor에서 아래 쿼리로 확인할 수 있습니다. 결과가 없으면 올바른 프로젝트의 DB에서 `auth-migration.sql`을 실행하세요.

```sql
select column_name
from information_schema.columns
where table_schema = 'public'
  and table_name = 'users'
  and column_name = 'auth_user_id';
```

마이그레이션보다 먼저 생성한 Auth 계정에는 가입 트리거가 소급 적용되지 않습니다. 기존 계정을 사용할 필요가 없다면 테스트 프로젝트의 해당 계정을 삭제한 뒤 마이그레이션 적용 후 다시 가입하세요. 같은 이메일의 기존 `public.users` 프로필도 자동 연결하지 않습니다. 기존 계정이나 주문을 보존하면서 사용하려면 아래의 명시적 계정 연결 절차가 필요합니다.

### 기존 회원을 연결할 때

기존 비밀번호는 자동 이관하지 않습니다. 먼저 테스트 환경에서 기존 이메일로 Supabase Auth 계정을 생성하고 이메일 소유권을 확인하세요. 이미 Auth에 있는 계정은 그 계정을 확인합니다. 운영 전환 시에는 검증된 초대/비밀번호 재설정 절차로 새 비밀번호를 설정해야 합니다. 그 후 SQL Editor에서 **실제 확인한 두 UUID**로 연결합니다. 이메일 일치만으로 일괄 연결하지 마세요.

```sql
-- 조회로 연결할 계정을 먼저 확인합니다.
select id, email, auth_user_id, role from public.users order by created_at;
select id, email, email_confirmed_at from auth.users order by created_at;

update public.users
set auth_user_id = '<확인한 auth.users.id>'::uuid
where id = '<기존 public.users.id>'::uuid and auth_user_id is null;

-- 신뢰하는 별도 테스트 계정 하나에만 관리자 역할을 부여합니다.
update public.users set role = 'admin'
where auth_user_id = '<관리자 auth.users.id>'::uuid and deleted_at is null;
```

주문이 참조하는 `public.users.id`는 변경하지 않습니다. 마이그레이션 전에 이미 생성된 Auth 계정도 이 절차로 연결해야 합니다. 신규 가입으로 자동 생성된 프로필은 별도 연결이 필요 없습니다. 운영 전환 완료 전까지 기존 해시는 보존하되, 이후 보관·삭제 방침을 별도로 결정하세요.

## 3. Windows PowerShell 로컬 실행 명령

Python 3.11 이상을 사용합니다. Node.js는 앱 실행에 필요하지 않습니다.

```powershell
Set-Location 'C:\AI4\Day12-Demo\project'
if (-not (Test-Path -LiteralPath '.\.venv\Scripts\python.exe')) {
    python -m venv .venv
}
.\.venv\Scripts\python.exe -m pip install -r requirements-test.txt
if (-not (Test-Path -LiteralPath '.\.env')) {
    Copy-Item -LiteralPath '.\.env.example' -Destination '.\.env'
}
```

기존 `.env`를 덮어쓰지 말고 아래 항목을 같은 테스트 프로젝트의 값으로 수정하세요.

```dotenv
APP_ORIGIN=http://127.0.0.1:8000
DATABASE_URL=postgresql://사용자:인코딩한비밀번호@호스트:5432/postgres
SUPABASE_URL=https://프로젝트ID.supabase.co
SUPABASE_KEY=publishable키_또는_anon키
SECRET_KEY=32자이상의무작위비밀키
SESSION_DAYS=7
COOKIE_SECURE=false
```

SECRET_KEY가 없거나 예시 값이면 아래 명령으로 한 번 생성해 저장합니다. 이미 유효한 키가 있으면 유지하세요. 키를 바꾸면 기존 암호화 토큰을 해독할 수 없어 다시 로그인해야 합니다. `.env`를 공유하거나 커밋하지 마세요.

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
.\.venv\Scripts\python.exe -m flask --app wsgi:application run --debug --no-reload --host 127.0.0.1 --port 8000
```

[http://127.0.0.1:8000/](http://127.0.0.1:8000/)으로 접속합니다. `localhost`로 바꾸면 APP_ORIGIN도 바꿔야 합니다. 종료는 `Ctrl+C`입니다. HTTPS 배포에서는 APP_ORIGIN을 실제 주소로, COOKIE_SECURE를 true로 변경합니다.

## 4. 자동 테스트 명령과 범위

앱을 실행하지 않은 별도 터미널에서도 실행할 수 있습니다. 실제 `.env`를 읽지 않고 Supabase Auth와 DB 경계를 테스트 대역으로 교체합니다.

```powershell
Set-Location 'C:\AI4\Day12-Demo\project'
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
# 인증·권한 관련 테스트만 실행
.\.venv\Scripts\python.exe -m pytest tests/test_auth_and_security.py tests/test_supabase_auth.py tests/test_members.py -q -p no:cacheprovider
# Node.js가 설치되어 있는 경우 선택적 프론트엔드 문법 검사
node --check static/js/app.js
```

검증 항목: 회원가입 입력 제한, 안전한 오류 응답, HttpOnly 쿠키, 토큰 암호화, 위조 쿠키 차단, 복사한 쿠키의 로그아웃 후 재사용 차단, 갱신 토큰 교체, Supabase 장애 처리, 관리자 접근 통제·즉시 권한 회수, role 주입 차단, 본인 주문/장바구니/결제/프로필 처리, 타인 접근 차단, CSRF, 재고·금액·결제 중복 방지.

실제 PostgreSQL 트랜잭션 검증은 **전용 테스트 DB**를 명시해야 실행됩니다. 임시 스키마를 만들고 테스트 후 삭제합니다. Supabase Auth는 이 테스트에서도 대역이며 Auth 트리거와 이메일 전송은 아래 수동 시나리오로 확인합니다.

```powershell
$env:RUN_DB_INTEGRATION_TESTS='1'
$env:TEST_DATABASE_CONFIRM_ISOLATED='I_WILL_USE_A_DEDICATED_TEST_DATABASE'
$env:TEST_DATABASE_URL='postgresql://전용테스트DB연결문자열'
.\.venv\Scripts\python.exe -m pytest tests/test_postgres_integration.py -q -p no:cacheprovider
Remove-Item Env:RUN_DB_INTEGRATION_TESTS, Env:TEST_DATABASE_CONFIRM_ISOLATED, Env:TEST_DATABASE_URL
```

## 5. 브라우저 수동 확인 순서

일반 회원 A/B와 관리자 C를 준비하고 서로 다른 브라우저 프로필 또는 시크릿 창을 사용하세요.

| 순서 | 확인 방법 | 기대 결과 |
| --- | --- | --- |
| 1 | 비로그인으로 상품 목록 확인 후 장바구니/회원정보 열기 | 상품 공개, 보호 화면은 로그인 안내 |
| 2 | A 신규 가입 → 이메일 인증 → 로그인 | 가입 접수 안내, 인증 후 로그인 성공, users의 auth_user_id 생성 |
| 3 | 잘못된 비밀번호·미인증 계정으로 로그인 | 실패 메시지, 로그인 쿠키 미발급 |
| 4 | A가 상품 담기 → 수량 변경 → 주문 → 모의 결제 → 구매내역 | 금액·재고 정상 반영, 중복 결제 차단 |
| 5 | A 주문 UUID를 기록하고 B로 동일 주문 상세·결제 API 호출 | 404, 주문/재고 변경 없음 |
| 6 | B로 `#/admin` 및 관리자 API 직접 호출 | 403, 상품/전체 주문 접근 불가 |
| 7 | C에게 SQL로 admin 부여 후 재로그인, 관리자 메뉴 열기 | 상품 등록·수정·재고 설정, 전체 주문·배송정보 확인 |
| 8 | C의 role을 customer로 SQL 변경 후 관리자 화면 새로고침 | 같은 세션에서도 403 |
| 9 | A가 프로필의 이름·연락처·주소 변경 | 본인만 갱신, role·email·id 추가 전송은 422 |
| 10 | 개발자도구 Cookies에서 쿠키 값을 기록 → 로그아웃 → 기록한 쿠키로 재요청 | 앱 보호 API 401 |
| 11 | 두 브라우저에서 A 로그인 → 한쪽에서 비밀번호 변경 | 기존 비밀번호 실패, 모든 앱 세션 401, 새 비밀번호로 로그인 가능 |
| 12 | JWT 만료 시간을 테스트 프로젝트에서 짧게 설정 후 로그인하고 만료 직전/이후 보호 API 호출 | 서버 자동 갱신, 브라우저 localStorage에 토큰 없음 |
| 13 | A 탈퇴 → 이전 쿠키·같은 비밀번호로 로그인 시도 | 차단, 기존 주문은 관리자에게 보존 |
| 14 | Supabase Data API에 anon 키/사용자 JWT로 users·orders·payments 직접 조회/수정 | 권한 오류 또는 행 미노출, 직접 변경 불가 |

일반 브라우저의 개발자도구 Console에서 아래와 같이 현재 로그인 세션으로 API 상태를 확인할 수 있습니다. `fetch`는 앱과 같은 출처의 페이지에서 실행하세요.

```javascript
// 비로그인 401 / 일반 회원 403 / 관리자 200
await fetch('/api/admin/orders', {credentials: 'same-origin'}).then(r => r.status)
// 회원 B로 로그인한 뒤 A의 주문 UUID를 사용하면 404
await fetch('/api/orders/<A의 주문 UUID>', {credentials: 'same-origin'}).then(r => r.status)
// 일반 회원도 role을 수정할 수 없음: 422
await fetch('/api/members/me', {
  method: 'PATCH', headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({role: 'admin'})
}).then(r => r.status)
```

## 6. 이번 작업에서 확인한 결과와 남은 확인

2026-10-30 로컬 자동 테스트 **117 passed, 1 skipped** 및 JavaScript 문법 검사를 통과했습니다. 실제 PostgreSQL 통합 테스트는 전용 DB 설정이 없어 건너뛰었습니다. 원격 DB 마이그레이션, 실제 이메일·Supabase 토큰 회전, 실제 브라우저 구매 시나리오, 배포는 아직 실행하지 않았습니다. 자동 테스트 성공이 실제 Supabase 연결 검증을 대신하지는 않습니다.

Supabase JWT 자체는 로그아웃 후에도 만료 시점까지 유효할 수 있습니다. 이 앱은 서버 세션 삭제와 DB 직접 접근 차단으로 로그아웃 후 앱 접근을 즉시 차단합니다. 만료된 앱 세션은 로그인 시 정리합니다. 대규모 운영에서는 주기적인 정리 작업을 추가할 수 있습니다.

## 7. 피드백 작성 양식

아래 내용을 이 채팅으로 보내주시면 재현 → 수정 → 관련 회귀 테스트 → 결과 갱신 순서로 개선합니다. 비밀번호·토큰·DB URI·SECRET_KEY는 보내지 마세요.

```text
테스트한 항목 번호:
사용한 역할: 비회원 / 일반 회원 A 또는 B / 관리자 C
실행 명령 또는 접속 화면:
재현 순서:
기대한 동작:
실제 동작 및 HTTP 상태/오류 메시지:
원하는 개선:
```

특히 이메일 인증을 필수로 유지할지, 상품·주문 관리 권한을 운영자/배송 담당자로 더 분리할지, 장바구니 보존 기간과 로그인 유지 기간이 적절한지 알려주세요. 실제 피드백은 아직 접수되지 않았습니다.

참고: [Supabase 사용자 확인](https://supabase.com/docs/reference/python/auth-getuser), [사용자 데이터와 가입 트리거](https://supabase.com/docs/guides/auth/managing-user-data), [로그아웃과 JWT 만료](https://supabase.com/docs/reference/javascript/auth-signout).
