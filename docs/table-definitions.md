> 이 문서는 이전 단계의 기록입니다. 현재 Supabase Auth 인증·서버 세션·권한·DB 전환은 [로컬 인증 테스트 안내](local-auth-testing.md)를 기준으로 확인하세요.

# 테이블 정의서

[ERD](erd.md) · [구매 시뮬레이션](purchase-simulation.md) · [schema.sql](../sql/schema.sql) · [seed.sql](../sql/seed.sql)

`public` 스키마를 사용합니다. **필수**는 NOT NULL, **선택**은 NULL 허용, `—`는 기본값 없음입니다. PK는 기본키, FK는 외래키, UNIQUE는 중복 불가입니다.

## users — 회원

| 컬럼 | 자료형 | 필수 여부 | 키·제약 | 기본값 |
| --- | --- | --- | --- | --- |
| id | uuid | 필수 | PK | gen_random_uuid() |
| email | varchar(254) | 필수 | UNIQUE, 소문자, 앞뒤 공백 없음, 빈 문자열 불가 | — |
| password_hash | text | 필수 | 해시 저장, 공백만 입력 불가 | — |
| name | varchar(100) | 필수 | 공백만 입력 불가 | — |
| phone | varchar(30) | 선택 | 연락처 | — |
| address | varchar(500) | 선택 | 주소 | — |
| deleted_at | timestamptz | 선택 | 탈퇴 시각 | — |
| created_at | timestamptz | 필수 | 가입 시각 | now() |
| updated_at | timestamptz | 필수 | 수정 시각 | now() |

`deleted_at IS NULL`이면 정상 회원입니다. 탈퇴 시 행을 삭제하지 않고 인증을 거부합니다. 탈퇴 후에도 이메일 중복 제한을 유지합니다.

## products — 상품

| 컬럼 | 자료형 | 필수 여부 | 키·제약 | 기본값 |
| --- | --- | --- | --- | --- |
| id | uuid | 필수 | PK | gen_random_uuid() |
| name | varchar(200) | 필수 | 공백만 입력 불가 | — |
| description | text | 필수 | 상품 설명 | 빈 문자열 |
| price | numeric(12,0) | 필수 | > 0 | — |
| stock | integer | 필수 | >= 0 | 0 |
| created_at | timestamptz | 필수 | 생성 시각 | now() |
| updated_at | timestamptz | 필수 | 수정 시각 | now() |

재고 0인 상품도 조회할 수 있지만 주문·결제는 차단합니다.

## orders — 장바구니·주문

주문 한 건의 공통 정보를 저장합니다. 선택 상품의 ID는 아래 `order_items.product_id`에 저장하고 `order_items.order_id`로 이 주문에 연결합니다. 회원 U1의 상품 P1 담기는 `orders(O1, U1)`과 `order_items(I1, O1, P1)` 두 행으로 표현합니다. 로그인한 회원 ID는 서버가 인증 결과에서 가져옵니다.

| 컬럼 | 자료형 | 필수 여부 | 키·제약 | 기본값 |
| --- | --- | --- | --- | --- |
| id | uuid | 필수 | PK | gen_random_uuid() |
| user_id | uuid | 필수 | FK → users.id, ON DELETE RESTRICT | — |
| status | varchar(20) | 필수 | cart / pending / paid | cart |
| total_amount | numeric(14,0) | 필수 | >= 0, 주문 생성 이후 > 0 | 0 |
| recipient_name | varchar(100) | 선택* | 수령인 | — |
| recipient_phone | varchar(30) | 선택* | 수령인 연락처 | — |
| shipping_address | varchar(500) | 선택* | 배송지 | — |
| ordered_at | timestamptz | 선택* | 주문 생성 시각 | — |
| paid_at | timestamptz | 선택 | paid에서만 필수, 다른 상태는 NULL | — |
| created_at | timestamptz | 필수 | 생성 시각 | now() |
| updated_at | timestamptz | 필수 | 수정 시각 | now() |

\* cart에서는 없어도 되지만 pending·paid에서는 필수입니다. 수령인·연락처·주소는 공백만 입력할 수 없습니다. cart의 ordered_at은 NULL입니다.

- 부분 UNIQUE: `user_id WHERE status = 'cart'` — 회원당 장바구니 최대 하나.
- 조회 인덱스: `(user_id, created_at DESC)`.
- 주문 시 배송정보를 확정하므로 이후 회원 주소 변경은 기존 주문에 영향을 주지 않습니다.

## order_items — 주문상품

이 테이블이 **주문과 상품의 연결 테이블**입니다. 한 O1 주문에 상품 P1·P2를 담으면 각각 별도 행으로 저장하며 두 행의 order_id는 모두 O1입니다.

| 컬럼 | 자료형 | 필수 여부 | 키·제약 | 기본값 |
| --- | --- | --- | --- | --- |
| id | uuid | 필수 | PK | gen_random_uuid() |
| order_id | uuid | 필수 | FK → orders.id, ON DELETE CASCADE | — |
| product_id | uuid | 필수 | FK → products.id, ON DELETE RESTRICT | — |
| product_name | varchar(200) | 필수 | 상품명 보관, 공백만 입력 불가 | — |
| quantity | integer | 필수 | > 0 | — |
| unit_price | numeric(12,0) | 필수 | > 0, 주문 시점 단가 | — |
| created_at | timestamptz | 필수 | 생성 시각 | now() |
| updated_at | timestamptz | 필수 | 수정 시각 | now() |

- 복합 UNIQUE: `(order_id, product_id)` — 같은 상품은 수량으로 합칩니다.
- 조회 인덱스: `product_id`. 복합 UNIQUE 인덱스는 order_id 조회도 지원합니다.
- 담은 시점의 가격·상품명을 저장하고 주문 생성 때 현재 값으로 확정합니다. pending 이후에는 수량·단가·상품명을 변경하지 않습니다.
- 장바구니 INSERT 단계부터 product_id·product_name·quantity·unit_price를 모두 저장합니다. product_id는 선택 상품을 식별하고 상품명·단가는 서버가 products에서 읽습니다.
- 행 금액은 `quantity × unit_price`, 주문 합계는 행 금액의 합입니다.

## payments — 모의 결제 결과

| 컬럼 | 자료형 | 필수 여부 | 키·제약 | 기본값 |
| --- | --- | --- | --- | --- |
| id | uuid | 필수 | PK | gen_random_uuid() |
| order_id | uuid | 필수 | FK → orders.id, ON DELETE RESTRICT | — |
| amount | numeric(14,0) | 필수 | > 0 | — |
| status | varchar(20) | 필수 | success / failed | — |
| failure_reason | varchar(500) | 선택 | 실패 시 공백 아닌 값 필수, 성공 시 NULL | — |
| created_at | timestamptz | 필수 | 결과 기록 시각 | now() |

- 부분 UNIQUE: `order_id WHERE status = 'success'` — 주문당 성공 최대 하나.
- 조회 인덱스: `(order_id, created_at DESC)`.
- 서버가 주문 합계로 결제금액을 결정하며 실제 카드정보는 저장하지 않습니다.

## 데이터 보존과 처리 책임

| 항목 | 처리 |
| --- | --- |
| 회원 탈퇴 | users.deleted_at 기록, 회원·주문·결제 행 보존 |
| 회원·상품 물리 삭제 | 참조하는 행이 있으면 RESTRICT로 차단 |
| 장바구니 삭제 | order_items도 CASCADE로 삭제 |
| 결제 기록이 있는 주문 삭제 | payments의 RESTRICT로 차단 |
| 주문 생성 이후 수정·삭제 | API가 주문상품 변경·주문 삭제를 제공하지 않음 |
| updated_at 갱신 | 후속 서비스 UPDATE 문에서 처리, 자동 트리거 없음 |

DB 제약은 잘못된 상태·수량·음수 재고·중복 성공을 막습니다. **재고 동시성, 주문 합계와 결제금액의 일치, 상태 전환은 후속 API의 트랜잭션으로 보장해야 합니다.** STEP 1 SQL만으로 구매 절차가 실행되지는 않습니다.

주문 생성·결제 시 주문 행을 잠근 뒤 상품 행을 ID 순서로 잠급니다. 결제 성공의 재고 차감·결제 기록·주문 변경은 함께 커밋합니다. 이미 결제된 주문의 재요청은 기존 성공 결과를 반환합니다.

장바구니 추가도 orders 생성·order_items 추가·합계 갱신을 한 트랜잭션으로 처리합니다. orders만 조회하면 상품은 보이지 않으므로 장바구니 화면은 order_items를 JOIN합니다. 구매내역은 회원의 paid 주문과 success 결제를 연결합니다. 상품별 행에 반복되는 주문 합계를 중복 합산하지 않습니다.

## 접근·인증

별도 세션 테이블이 필요 없는 **JWT + HttpOnly 쿠키**를 선택합니다. 비밀번호 해시, 로그아웃, 탈퇴 확인, CSRF 방어는 후속 단계에서 구현합니다.

Flask WSGI 앱만 서버 전용 PostgreSQL 연결로 접근합니다. SQL은 모든 테이블에 RLS를 적용하고 anon·authenticated 권한을 회수합니다. RLS 우회 서버 역할의 소유권 검증은 앱이 담당합니다. 연결 비밀은 환경변수로 관리합니다.

## 사용자 확인 방법

1. 신규 Supabase SQL Editor에서 schema.sql을 실행합니다.
2. 성공하면 seed.sql을 실행합니다.
3. Table Editor에서 테이블 5개, 상품 5개, 메모 노트 재고 0을 확인합니다.
4. seed.sql 재실행 후에도 중복 상품이 없는지 확인합니다.

schema.sql은 신규 생성용으로 동명 테이블이 있으면 중단합니다. seed.sql은 기존 샘플의 가격·재고를 덮어쓰지 않습니다. 이번 수정에서 SQL은 실행하지 않았습니다.

## 가정

- 금액은 KRW 정수 원 단위, 시각은 timestamptz로 저장하고 화면에서 한국 시간으로 표시합니다.
- 연락처·주소는 가입 시 선택, 주문 생성 시 필수입니다.
- 배송비·할인·별도 세금 계산, 옵션·취소·환불은 포함하지 않습니다.
- 탈퇴 이메일 재사용은 허용하지 않습니다.
