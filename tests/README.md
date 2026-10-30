> Supabase Auth 전환 후 실행 명령과 실제 서비스 확인 범위는 [로컬 인증 테스트 안내](../docs/local-auth-testing.md)를 먼저 확인하세요. 자동 테스트는 Auth를 테스트 대역으로 교체하며 실제 이메일 전송을 검증하지 않습니다.

# 쇼핑몰 API pytest 안내

## 검증 범위

- 설정 검증, 비밀번호 해시, JWT 만료·변조·클레임, 쿠키 보안 속성, 회원가입·로그인·로그아웃, CSRF 출처 차단
- 비로그인 상품 목록·상세, 페이지 입력값, 상품 없음·품절 표시
- 로그인 필수 API, 회원별 장바구니 분리, 상품 추가·중복 추가·수량 변경·삭제, 합계와 재고 검증
- 장바구니 주문과 바로 주문, 배송 입력 검증, 사용자별 주문 조회
- 결제 실패 후 재시도, 재고 부족 기록, 성공 후 중복 결제 방지, 금액 불일치와 재고 변경 롤백
- 회원정보 부분 수정, 비밀번호 재확인·변경, 탈퇴 후 인증 차단과 구매내역 보존, 회원별 구매내역 조회
- 실제 PostgreSQL의 SQL·제약조건까지 확인하는 선택형 통합 시나리오

일반 테스트는 현재 라우터와 서비스 코드를 실행하고 SQL 경계만 메모리 저장소로 바꿉니다. 따라서 PostgreSQL의 쿼리 문법, 제약조건, 실제 동시 잠금 동작을 증명하지는 않습니다. 그 부분은 아래의 별도 통합 테스트로 확인합니다.

## 기본 테스트 설치 및 실행

PowerShell에서 `C:\AI4` 폴더에 있을 때 실행합니다. 이 명령은 프로젝트의 실제 `.env`를 읽지 않으며 테스트용 저장소만 사용합니다.

```powershell
python -m pip install -r .\Day12-Demo\project\requirements-test.txt
python -m pytest -c .\Day12-Demo\project\pytest.ini .\Day12-Demo\project\tests -m "not integration" -q
```

이 단계에서는 위 명령을 실행하지 않았습니다. 작성 결과를 확인하고 사용자가 실행 진행 피드백을 주면 실행합니다.

## 선택형 PostgreSQL 통합 테스트

기본 테스트와 분리하여 전용 테스트 DB 연결 문자열을 명시했을 때만 수행합니다. 연결 문자열은 `.env`에서 가져오지 않습니다. 테스트는 무작위 `shop_test_<UUID>` 스키마를 만들고 그 스키마 안에서만 테이블을 생성한 뒤, 종료할 때 해당 스키마를 삭제합니다. 실제 운영 데이터베이스를 테스트용으로 지정하지 마세요.

전용 테스트 DB를 준비한 다음 PowerShell 세션에 별도 환경변수를 설정합니다.

```powershell
$env:RUN_DB_INTEGRATION_TESTS = "1"
$env:TEST_DATABASE_CONFIRM_ISOLATED = "I_WILL_USE_A_DEDICATED_TEST_DATABASE"
$env:TEST_DATABASE_URL = "전용 테스트 DB의 PostgreSQL 연결 문자열"
python -m pytest -c .\Day12-Demo\project\pytest.ini .\Day12-Demo\project\tests -m integration -q
```

실행 후 환경변수를 지우려면 다음을 사용합니다.

```powershell
Remove-Item Env:RUN_DB_INTEGRATION_TESTS, Env:TEST_DATABASE_CONFIRM_ISOLATED, Env:TEST_DATABASE_URL
```

## 보고 시 필요한 정보

실행 후 pytest의 통과·실패 요약과 실패한 테스트의 오류 전문을 알려주세요. 인증 정보, `.env` 값, 전체 DB 연결 문자열은 공유하지 마세요.
