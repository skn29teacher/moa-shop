# 모아샵: SQLite + Supabase Auth + Groq AI 채팅

문서 기준일: 2026-11-06. 현재 로컬 구현을 설명합니다. PythonAnywhere의 기존 쇼핑몰 배포와 새 AI 기능의 배포 여부는 구분하며, 서버 업데이트 후 별도로 점검합니다.

## AI 쇼핑 도우미 — Groq 무료 API

첫 접속 화면과 `/#/chat`에서 AI 쇼핑 도우미를 이용할 수 있습니다. 기존 쇼핑 화면은 상단의 **상품** 메뉴로 이동합니다.

`GROQ_API_KEY`를 서버 `.env`에 설정하면 Groq의 실제 모델을 호출합니다. DB 공개 상품 목록과 등록 문서에서 검색한 구간을 참고하고 최근 대화를 이어갑니다. 로딩·오류·재시도, 마크다운 표·목록·코드 렌더링, 참고 문서 표시와 데모 요청 제한을 제공합니다. 대화는 화면 메모리에만 유지하며 질문·최근 대화·공개 상품 정보·검색된 문서 구간은 Groq에 전송됩니다. 첨부·주문 실행·대화 저장은 제공하지 않습니다. 키가 없으면 쇼핑몰과 가상 대화 예시를 사용할 수 있습니다.

**[Groq 가입·API 키 발급·로컬 명령어·테스트·PythonAnywhere 배포 가이드](docs/GROQ_CHAT.md)**

AI가 참고할 공개 정책·FAQ는 **[knowledge 폴더](knowledge/README.md)**에 UTF-8 `.md`·`.txt`로 등록합니다. 질문과 관련된 구간을 검색해 Groq에 전달하며 화면에 참고 파일명·행 범위를 표시합니다. 검색 확인: `python -m flask --app wsgi:application check-chat-docs --query "환불"`.

운영자용 `docs/` 문서는 AI가 자동으로 읽지 않습니다. AI 참고 자료는 `knowledge/`에 별도로 등록하며, 시스템 지시문은 `app/services/chat.py`의 `SYSTEM_PROMPT`에서 관리합니다. 기본 문서는 화면 이용 안내이고, 실제 환불 정책은 아직 등록하지 않았습니다.

상품·회원 프로필·장바구니·주문·모의 결제·앱 세션은 Python 내장 SQLite 파일에 저장합니다. 이메일 계정과 비밀번호 검증은 Supabase Auth가 HTTPS로 처리합니다. 앱은 Supabase PostgreSQL에 직접 연결하지 않으며 DATABASE_URL과 psycopg를 사용하지 않습니다.

## 문서 읽는 순서

| 문서 | 설명 |
| --- | --- |
| [Groq AI 채팅](docs/GROQ_CHAT.md) | 가입·키 발급, 모델 연결, 문서 검색, API 응답, 제한과 오류 해결 |
| [AI 참고 문서 관리](knowledge/README.md) | 공개 정책·FAQ 등록, 검색 방식과 제한, 문서 수정 반영 및 출처의 의미 |
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
.\.venv\Scripts\python.exe -m flask --app wsgi:application check-chat-docs
.\.venv\Scripts\python.exe -m flask --app wsgi:application run --debug --no-reload --host 127.0.0.1 --port 8000
```

## 현재 제공하는 기능

배포 ZIP은 `project/`에서 `.\.venv\Scripts\python.exe scripts/package_deploy.py`로 직접 생성합니다. 결과는 `dist/moashop-sqlite-deploy.zip`입니다. 실제 `.env`·DB·가상환경을 제외하는 구성과 업로드·압축 해제 명령은 [배포 문서](docs/DEPLOYMENT.md#2-2-올릴-파일과-zip-내부-구조)에 있습니다.

AI 연결 확인은 `check-groq`, 실제 답변 생성 확인은 `check-groq --generate`입니다. 후자는 무료 API 할당량을 사용합니다. `check-chat-docs --query "장바구니"`는 외부 호출 없이 문서 검색만 확인합니다. 모든 명령은 `project/` 폴더에서 실행합니다.

비회원은 상품 목록과 상세를 볼 수 있습니다. 회원은 자신의 장바구니·주문·구매내역·프로필을 사용하고 비밀번호 변경과 탈퇴를 할 수 있습니다. 관리자는 상품 등록·가격·재고 수정과 전체 고객 주문 조회를 할 수 있습니다. 결제는 모의 결제이며 실제 PG 결제·환불·배송 상태 변경은 구현하지 않았습니다.

이메일 인증 완료 뒤에는 `/auth/confirm`에서 URL의 인증 결과를 정리하고 `/#/login`으로 이동합니다. **Supabase URL Configuration의 Site URL과 Redirect URLs 설정도 필요합니다.** `localhost:3000`으로 이동하는 문제의 해결 방법은 [배포 문서](docs/DEPLOYMENT.md)에 있습니다.

기존 Supabase Auth 계정은 계속 사용할 수 있습니다. 기존 PostgreSQL 쇼핑몰 데이터는 자동 이관하지 않으며 현재 앱은 원격 프로필·상품·주문 테이블을 읽지 않습니다. `sql/legacy-postgres-schema.sql`, `sql/auth-migration.sql`, `sql/reset-shop-db.sql`과 기존 별도 도식 파일은 이전 구조의 참고 자료입니다. 현재 초기화에는 `sql/schema.sql`과 `sql/seed.sql`만 사용합니다.
