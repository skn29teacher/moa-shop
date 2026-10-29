# STEP 3 — 상품·장바구니·주문·모의 결제 API

[README](../README.md) · [인증 안내](step-2-auth.md) · [테이블 정의서](table-definitions.md)

이번 단계는 API와 사용자 확인 안내를 작성했습니다. 서버 실행·설치·DB 접속·SQL 실행·브라우저 조작·자동 테스트는 수행하지 않았습니다.

## 1. 생성·수정 파일

| 경로 | 역할 |
| --- | --- |
| app/schemas/products.py | 상품 목록·상세 응답 |
| app/schemas/orders.py | 수량·배송정보·주문 입력과 장바구니·주문 응답 |
| app/schemas/payments.py | 모의 결제 요청·결과 응답 |
| app/db/products.py | 상품 조회·일정한 ID 순서의 잠금·재고 차감 SQL |
| app/db/commerce.py | 회원·주문 잠금, 장바구니·주문상품·결제 SQL |
| app/services/commerce_common.py | 회원 확인·금액 범위·재고 검증·응답 구성 |
| app/services/products.py | 상품 조회 처리 |
| app/services/cart.py | 본인 장바구니 조회·추가·수량 변경·삭제 |
| app/services/orders.py | 장바구니 주문·바로 구매·주문 상세 |
| app/services/payments.py | 실패 결과 보존·결제 성공·중복 재고 차감 방지 |
| app/routers/products.py | 공개 상품 API |
| app/routers/cart.py | 인증이 필요한 장바구니 API |
| app/routers/orders.py | 인증이 필요한 주문 생성·상세 API |
| app/routers/payments.py | 인증이 필요한 모의 결제 API |
| app/db/connection.py | autocommit 연결과 서비스별 명시적 트랜잭션 사용 |
| app/main.py | 새 라우터 등록·버전 갱신 |
| README.md | API 목록·현재 단계·실행 안내 갱신 |
| docs/step-3-shopping.md | Swagger 호출 순서·기대 결과 |

기존 SQL 테이블·환경변수·requirements.txt는 변경하지 않았습니다. 상품 조회를 제외한 새 API는 로그인 쿠키가 필요합니다. 다른 회원의 주문은 404로 응답합니다.

## 2. 실행 방법

이미 사용 중인 `C:\AI4\.venv` 등 가상환경이 활성화된 PowerShell에서 실행하세요. 기존 Uvicorn이 실행 중이면 --reload가 변경을 반영합니다. 수동 재시작이 필요하면 기존 프로세스를 Ctrl+C로 종료한 뒤 실행합니다.

```powershell
Set-Location 'C:\AI4'
python -m uvicorn app.main:app --app-dir .\Day12-Demo\project --reload --reload-dir .\Day12-Demo\project\app --host 127.0.0.1 --port 8000
```

[Swagger](http://127.0.0.1:8000/docs)를 새로고침하고 상품·장바구니·주문·모의 결제 그룹을 확인합니다. APP_ORIGIN과 같은 주소를 사용해야 합니다. 새 라이브러리 설치나 schema.sql 재실행은 필요하지 않습니다.

## 3. API 목록

| 메서드 | 경로 | 인증 | 성공 응답 |
| --- | --- | --- | --- |
| GET | /api/products | 불필요 | 200, items·total·limit·offset |
| GET | /api/products/{product_id} | 불필요 | 200, 상품 정보 |
| GET | /api/cart | 필요 | 200, 장바구니·items |
| POST | /api/cart/items | 필요 | 200, 갱신된 장바구니 |
| PATCH | /api/cart/items/{product_id} | 필요 | 200, 갱신된 장바구니 |
| DELETE | /api/cart/items/{product_id} | 필요 | 200, 갱신된 장바구니 |
| POST | /api/orders | 필요 | 201, pending 주문·items |
| GET | /api/orders/{order_id} | 필요 | 200, 본인 pending/paid 주문 |
| POST | /api/orders/{order_id}/payments | 필요 | 200, payment·order_status·already_paid |

상품 목록의 limit 기본값은 20, 최대 100이고 offset 기본값은 0입니다. 모든 금액은 정수 원입니다. 장바구니/주문 items에는 product_id·product_name·quantity·unit_price·line_amount가 있으며, 장바구니 items에는 현재 stock도 포함됩니다.

## 4. Swagger 기본 구매 시나리오

아래 상품 UUID는 STEP 1 seed.sql의 베이직 반팔 티셔츠입니다. seed를 넣지 않았다면 목록에서 실제 상품 UUID를 복사해서 사용하세요. 상품이 하나도 없다면 seed.sql은 사용자가 직접 실행합니다.

### ① 비로그인 상품 조회

GET /api/products에서 limit=20, offset=0으로 Execute합니다. GET /api/products/{product_id}에는 아래 UUID를 넣습니다.

```text
10000000-0000-4000-8000-000000000001
```

200과 상품명·price·stock을 확인합니다. 이후 2개를 주문할 예정이므로 현재 stock이 2 이상인 상품을 선택하세요. 최초 재고를 S로 기록합니다. 예시 상품의 기본 단가는 19,000원입니다.

### ② 로그인

POST /api/auth/login에서 STEP 2에 가입한 계정으로 로그인합니다.

```json
{
  "email": "buyer@example.com",
  "password": "ShopDemo2026!"
}
```

본인이 다른 비밀번호로 가입했다면 그 값을 사용합니다. 같은 브라우저가 HttpOnly 쿠키를 보냅니다. Swagger Authorize에 쿠키 값을 복사하지 않습니다.

### ③ 빈 장바구니 확인

GET /api/cart를 호출합니다. 처음이면 id=null, total_amount=0, items=[]입니다. 조회만으로 DB에 장바구니 행을 만들지 않습니다. 이미 담긴 상품이 있다면 DELETE API로 정리하거나 해당 상품을 고려해 합계를 확인하세요.

### ④ 상품 1개 담기

POST /api/cart/items:

```json
{
  "product_id": "10000000-0000-4000-8000-000000000001",
  "quantity": 1
}
```

200, status=cart, total_amount=19000을 확인합니다. orders에는 회원 ID, order_items에는 해당 order_id와 선택한 product_id가 함께 저장됩니다. 상품명·단가는 서버가 읽어 저장하며 요청에서 받지 않습니다. stock은 S를 유지합니다.

### ⑤ 수량을 2개로 변경

PATCH /api/cart/items/{product_id}의 경로에는 티셔츠의 상품 UUID를 넣습니다. order_items.id나 orders.id를 넣지 않습니다.

```json
{
  "quantity": 2
}
```

200, quantity=2, line_amount=38000, total_amount=38000을 확인합니다. PATCH는 절대 수량 설정이고 POST는 기존 수량에 더하기입니다. 재고는 여전히 S입니다.

### ⑥ 장바구니 삭제 확인 후 다시 담기

같은 상품 UUID로 DELETE /api/cart/items/{product_id}를 호출합니다. 200, items=[], total_amount=0입니다. 빈 cart 행은 유지됩니다. 다음 주문을 위해 POST /api/cart/items에 quantity=2로 다시 담으세요.

### ⑦ 장바구니 전체 주문 생성

POST /api/orders에서 source=cart 형태를 선택하거나 아래 JSON을 넣습니다.

```json
{
  "source": "cart",
  "recipient_name": "김구매",
  "recipient_phone": "010-1234-5678",
  "shipping_address": "서울시 예시로 10"
}
```

201, status=pending과 주문 id를 복사합니다. 단가·상품명·배송지·합계를 확정하고 cart였던 같은 주문 행의 상태를 바꿉니다. **재고는 S 그대로이며 예약하지 않습니다.** 이후 GET /api/cart는 새로운 cart가 없으면 빈 결과를 반환합니다.

GET /api/orders/{order_id}에 복사한 주문 UUID를 넣으면 확정된 주문이 보입니다.

### ⑧ 모의 결제 실패

POST /api/orders/{order_id}/payments의 경로에 위 주문 UUID를 넣습니다.

```json
{
  "simulate_success": false
}
```

HTTP 200, payment.status=failed, failure_reason="모의 결제 실패", order_status=pending입니다. 결제 시도 자체는 정상 처리되었지만 모의 결과가 실패인 경우입니다. 실패 기록은 payments에 남고 재고는 S입니다.

### ⑨ 같은 주문의 모의 결제 성공

같은 경로에서 다음을 보냅니다.

```json
{
  "simulate_success": true
}
```

200, payment.status=success, order_status=paid, already_paid=false입니다. 결제금액은 서버가 주문 합계 38,000원으로 정합니다. 상품 상세를 다시 조회하면 stock=S-2입니다. GET 주문 상세에는 paid_at이 생깁니다. 앞선 실패 행도 보존됩니다.

### ⑩ 동일 결제 재요청

⑨와 같은 요청을 반복합니다. 200, already_paid=true이며 **기존 성공 payment.id가 그대로 반환**됩니다. payments에 성공 행이 추가되지 않고 stock도 S-2를 유지합니다. 이미 paid이면 simulate_success=false를 보내도 기존 성공 결과를 반환합니다.

## 5. 바로 구매 시나리오

기존 장바구니에 다른 상품을 담아 둔 뒤 POST /api/orders에 다음을 보냅니다.

```json
{
  "source": "buy_now",
  "product_id": "10000000-0000-4000-8000-000000000001",
  "quantity": 1,
  "recipient_name": "김구매",
  "recipient_phone": "010-1234-5678",
  "shipping_address": "서울시 예시로 10"
}
```

201의 별도 pending 주문이 생성됩니다. GET /api/cart에서 기존 cart가 그대로인지 확인합니다. 새 order_id로 결제하면 선택 상품 1개만 결제합니다.

## 6. 재고 부족·입력·접근 검증

### 이미 품절된 상품

seed.sql의 메모 노트 UUID는 다음과 같습니다.

```text
10000000-0000-4000-8000-000000000005
```

이 상품의 stock=0을 확인하고 장바구니 추가 또는 buy_now 주문을 시도하면 409입니다. 장바구니 변경과 주문 생성은 롤백되고 주문·결제 성공 기록은 생기지 않습니다.

### 주문 후 결제 직전에 재고가 부족해진 경우

이 시나리오는 샘플 재고를 실제로 소진합니다. 재고 S가 1 이상인 샘플 상품을 선택하고, quantity=S인 buy_now 주문 A와 B를 각각 생성합니다. 주문 생성은 재고를 예약하지 않으므로 둘 다 pending으로 생성됩니다.

1. A를 결제하면 stock=0, A는 paid입니다.
2. B를 결제하면 HTTP 409지만 응답 본문에는 payment.status=failed, failure_reason에 재고 부족, order_status=pending이 있습니다.
3. payments에서 B의 실패 행을 확인하고 stock이 음수가 아닌 0인지 확인합니다.

재고 부족 응답은 실패 기록을 커밋한 뒤 반환합니다. 반면 DB 연결 오류·트랜잭션 오류는 중간 변경을 전부 롤백하며, 저장할 수 없는 실패 기록을 저장했다고 응답하지 않습니다.

### 입력과 접근 권한

| 요청 | 기대 결과 |
| --- | --- |
| quantity=0 또는 음수 | 422, 변경 없음 |
| quantity="2" 또는 true | 422, 정수 JSON 값만 허용 |
| 재고보다 많은 수량 | 409, 변경 없음 |
| 존재하지 않는 상품 UUID | 404 |
| 장바구니에 없는 상품 변경·삭제 | 404 |
| 빈 장바구니 주문 | 409 |
| 공백 수령인·주소 또는 잘못된 연락처 | 422 |
| amount·unit_price·user_id 등 미정의 입력 필드 | 422 |
| 비로그인 상품 목록·상세 | 200 |
| 로그아웃 후 장바구니·주문·결제 | 401 |
| 다른 회원의 주문 상세·결제 | 404, 변경 없음 |
| cart ID를 결제 경로에 사용 | 409 |

다른 회원의 주문 접근은 계정 A에서 주문 ID를 기록하고 로그아웃한 뒤, 계정 B로 로그인하여 같은 ID를 호출해 확인합니다.

## 7. 테이블별 처리와 동시성

| 요청 | 저장 내용 |
| --- | --- |
| 상품 조회 | products 읽기만 수행 |
| 장바구니 추가 | 회원당 cart 생성/재사용, order_items 추가 또는 수량 증가, 합계 갱신 |
| 수량 변경·삭제 | 본인 cart의 상품 행 변경, 합계 재계산 |
| cart 주문 | 현재 가격·이름 확정, 배송정보 저장, pending 전환 |
| buy_now 주문 | 기존 cart 유지, 별도 pending 주문과 상품 행 생성 |
| 결제 실패 | failed 결제 행 추가, 주문은 pending, 재고 차감 없음 |
| 결제 성공 | 재고 차감 + success 결제 + paid 전환을 함께 커밋 |

동일 회원의 장바구니 최초 생성과 변경은 users 행 잠금으로 직렬화합니다. 변경 요청은 회원 → 주문 → 상품(ID 순서)로 잠그고, 다른 회원의 결제가 같은 상품 재고를 함께 소진하지 못하게 합니다. DB의 음수 재고 CHECK와 주문당 성공 결제 UNIQUE도 유지합니다.

연결 풀은 autocommit을 사용하고, 변경 서비스는 명시적 transaction() 안에서 처리합니다. 인증 SELECT가 바깥 트랜잭션을 만들어 실제 커밋을 응답 뒤로 미루는 상황을 피했습니다. 각 서비스는 커밋이 완료된 뒤 결과를 반환합니다.

## 8. 사용자 확인 체크리스트

- [ ] 비로그인 상품 목록·상세가 200이다. O/X
- [ ] 로그인 후 장바구니 추가·수량 변경·삭제가 된다. O/X
- [ ] 주문 생성 시 pending이며 단가·배송정보가 저장된다. O/X
- [ ] 바로 구매 시 기존 장바구니가 유지된다. O/X
- [ ] 모의 결제 실패 후 재고가 그대로이고 실패 기록이 남는다. O/X
- [ ] 결제 성공 후 재고가 구매 수량만큼 줄고 paid가 된다. O/X
- [ ] 같은 결제를 반복해도 성공 ID와 재고가 유지된다. O/X
- [ ] 재고 부족 결제는 409·failed이며 재고가 음수가 되지 않는다. O/X
- [ ] 비로그인 보호 API는 401, 다른 회원 주문은 404다. O/X

## 9. 가정

- cart 주문은 장바구니 전체를 확정합니다. 선택 상품만 결제할 때는 buy_now를 사용합니다.
- 재고는 주문 생성 때 예약하지 않고 결제 성공 때 차감합니다.
- 담긴 상품의 가격은 주문 생성 시 현재 가격으로 확정하며 pending 이후에는 바꾸지 않습니다.
- 결제 대기 주문은 수량·배송정보를 수정하지 않으며 필요하면 새 주문을 만듭니다. 취소·환불은 구현하지 않습니다.
- 모의 결제 결과는 simulate_success로 지정하며 카드정보·실제 PG는 사용하지 않습니다.
- 실패 결제의 재시도마다 실패 행이 생길 수 있지만 성공 행은 주문당 하나입니다.
- 프론트엔드 로그인 화면 이동·복귀와 구매내역 목록은 후속 단계에서 구현합니다.
- 읽기·코드 검토만 진행했으며 실행 확인은 사용자의 결과를 기다립니다.

확인 후 결과나 수정사항을 알려주세요. STEP 4는 사용자 지시 후 진행합니다.
