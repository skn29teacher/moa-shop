# STEP 5 — 쇼핑몰 화면 확인

## 화면과 API 연결

페이지는 `/#/` 아래 해시 경로로 이동합니다. HTML은 Flask가 `/`에서 제공하고, CSS와 JavaScript는 `/static`에서 제공합니다.

| 화면 | 주소 | 연결 API |
| --- | --- | --- |
| 상품목록 | `/#/products` | `GET /api/products` |
| 상품상세 | `/#/products/{product_id}` | `GET /api/products/{product_id}`, 장바구니 추가, 바로 주문 |
| 로그인 | `/#/login` | `POST /api/auth/login` |
| 회원가입 | `/#/signup` | `POST /api/auth/signup` |
| 장바구니 | `/#/cart` | 장바구니 조회·수정·삭제 |
| 주문서 | `/#/checkout?source=cart` 또는 바로 주문 쿼리 | `POST /api/orders` |
| 모의 결제 | `/#/payment?order_id={order_id}` | 주문 조회, `POST /api/orders/{order_id}/payments` |
| 회원정보 | `/#/account` | 회원정보 조회·수정, 비밀번호 변경, 탈퇴 |
| 구매내역 | `/#/orders` | `GET /api/members/me/orders` |

로그인이 필요한 API가 401을 반환하면 화면에 로그인 링크를 표시합니다. 요청한 원래 화면으로 자동 복귀하는 동작은 STEP 6에서 연결합니다.

## 실행

PowerShell에서 프로젝트 폴더로 이동한 뒤 서버를 실행하고 `http://127.0.0.1:8000/`을 엽니다.

```powershell
Set-Location 'C:\AI4\Day12-Demo\project'
python -m flask --app wsgi:application run --debug --no-reload --host 127.0.0.1 --port 8000
```

## 브라우저 확인 체크리스트

개발자 도구(F12)의 반응형 기기 모드에서 **360px**, **768px**, **1200px** 너비를 각각 확인합니다.

- [ ] 상품 목록과 상세에서 상품명·가격·품절 상태가 표시된다.
- [ ] 상세의 수량 선택, 장바구니 추가, 바로 주문이 동작한다.
- [ ] 회원가입 후 로그인할 수 있고, 로그아웃하면 메뉴가 바뀐다.
- [ ] 장바구니에서 수량 변경과 삭제가 되고 합계가 갱신된다.
- [ ] 주문서 생성 후 모의 결제 성공·실패 결과를 확인할 수 있다.
- [ ] 회원정보 수정, 비밀번호 변경, 탈퇴 화면이 동작한다.
- [ ] 구매내역에 주문 상태와 주문 시점 상품·금액이 표시된다.
- [ ] 360px에서 가로 스크롤 없이 버튼과 입력란을 사용할 수 있다.
- [ ] 768px 태블릿과 1200px 데스크톱에서 내용 폭과 카드 배치가 자연스럽다.
- [ ] 비로그인 상태에서 보호 화면에 들어가면 로그인 안내가 보인다.

이번 단계에서는 브라우저 조작이나 화면 검증을 수행하지 않습니다. 직접 확인한 화면 크기와 문제를 알려주면 해당 파일만 수정합니다.
