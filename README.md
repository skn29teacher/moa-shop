# 모아샵: SQLite + Supabase Auth

Flask 쇼핑몰의 현재 구현과 배포 방법을 설명하는 문서 모음입니다. 기준일은 2026-10-30입니다. 이전 단계별 Markdown 문서는 모두 교체했습니다.

상품·회원 프로필·장바구니·주문·모의 결제·앱 세션은 Python 내장 SQLite 파일에 저장합니다. 이메일 계정과 비밀번호 검증은 Supabase Auth가 HTTPS로 처리합니다. 앱은 Supabase PostgreSQL에 직접 연결하지 않으며 DATABASE_URL과 psycopg를 사용하지 않습니다.

## 문서 읽는 순서

| 문서 | 설명 |
| --- | --- |
| [PythonAnywhere 배포](docs/DEPLOYMENT.md) | 이번에 진행한 로그인 → ZIP 업로드 → 가상환경 → .env → DB 준비 → WSGI → Reload 과정과 오류 해결 |
| [코드 구조와 SQLite](docs/ARCHITECTURE.md) | 폴더별 책임, 요청 처리, 테이블 관계, 구매 트랜잭션, API 목록 |
| [Supabase Auth와 SQLite 연동](docs/AUTH.md) | 가입·이메일 인증·로그인·세션·토큰 갱신·권한·비밀번호 변경·탈퇴의 실제 동작 |
| [로컬 실행과 테스트](docs/LOCAL_TESTING.md) | Windows 실행 명령, 자동 테스트, 역할별 수동 테스트와 피드백 양식 |

## 실행 환경

Python 3.11 이상과 SQLite 3.35 이상이 필요합니다. 이번 PythonAnywhere 배포에서는 Python 3.13.1, SQLite 3.37.2를 확인했습니다. Flask, Pydantic, pydantic-settings, email-validator, cryptography를 사용합니다. 프론트엔드는 순수 HTML·CSS·JavaScript이며 Node.js는 서버 실행에 필요하지 않습니다.

로컬 주소는 [http://127.0.0.1:8000/](http://127.0.0.1:8000/), 배포 주소는 [https://kyuyounglee.pythonanywhere.com/](https://kyuyounglee.pythonanywhere.com/)입니다. 로컬과 배포 서버는 서로 다른 SQLite 파일을 사용합니다.

## 빠른 실행

아래 명령은 가상환경과 실제 `.env` 설정이 준비된 뒤 실행합니다. 처음 준비하는 경우 [로컬 실행 문서](docs/LOCAL_TESTING.md)를 따라가세요.

```powershell
Set-Location 'C:\AI4\Day12-Demo\project'
.\.venv\Scripts\python.exe -m flask --app wsgi:application init-db
.\.venv\Scripts\python.exe -m flask --app wsgi:application seed-demo
.\.venv\Scripts\python.exe -m flask --app wsgi:application run --debug --no-reload --host 127.0.0.1 --port 8000
```

## 현재 제공하는 기능

비회원은 상품 목록과 상세를 볼 수 있습니다. 회원은 자신의 장바구니·주문·구매내역·프로필을 사용하고 비밀번호 변경과 탈퇴를 할 수 있습니다. 관리자는 상품 등록·가격·재고 수정과 전체 고객 주문 조회를 할 수 있습니다. 결제는 모의 결제이며 실제 PG 결제·환불·배송 상태 변경은 구현하지 않았습니다.

이메일 인증 완료 뒤에는 `/auth/confirm`에서 URL의 인증 결과를 정리하고 `/#/login`으로 이동합니다. **Supabase URL Configuration의 Site URL과 Redirect URLs 설정도 필요합니다.** `localhost:3000`으로 이동하는 문제의 해결 방법은 [배포 문서](docs/DEPLOYMENT.md)에 있습니다.

기존 Supabase Auth 계정은 계속 사용할 수 있습니다. 기존 PostgreSQL 쇼핑몰 데이터는 자동 이관하지 않으며 현재 앱은 원격 프로필·상품·주문 테이블을 읽지 않습니다. `sql/legacy-postgres-schema.sql`, `sql/auth-migration.sql`, `sql/reset-shop-db.sql`과 기존 별도 도식 파일은 이전 구조의 참고 자료입니다. 현재 초기화에는 `sql/schema.sql`과 `sql/seed.sql`만 사용합니다.
