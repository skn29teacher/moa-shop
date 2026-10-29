# STEP 4 — 회원정보·구매내역 API

모든 경로는 로그인 쿠키가 필요합니다. 회원 응답에는 비밀번호 해시와 탈퇴 시각을 포함하지 않습니다.

## API

| Method | Path | 설명 |
| --- | --- | --- |
| `GET` | `/api/members/me` | 내 회원정보 조회 |
| `PATCH` | `/api/members/me` | 이름·연락처·주소 중 전달한 항목 수정 |
| `PUT` | `/api/members/me/password` | 현재 비밀번호 확인 후 변경 |
| `DELETE` | `/api/members/me` | 회원을 soft delete하고 로그인 쿠키 제거 |
| `GET` | `/api/members/me/orders` | 내 주문·구매내역 조회 |

## 요청 예시

회원정보 일부 수정:

```json
{
  "name": "김테스트",
  "phone": "010-1234-5678",
  "address": "서울시 예시로 10"
}
```

연락처 또는 주소는 빈 문자열이나 `null`로 지울 수 있습니다. 이름은 비워둘 수 없습니다. 수정할 항목을 하나 이상 보내야 합니다.

비밀번호 변경:

```json
{
  "current_password": "현재 비밀번호",
  "new_password": "새 비밀번호 8자 이상"
}
```

현재 비밀번호가 틀리면 `400`, 입력 형식이 유효하지 않으면 `422`를 반환합니다.

## 구매내역 기준

`cart` 상태는 구매내역에서 제외합니다. `pending` 주문과 `paid` 주문을 최근 주문부터 반환하고, 각 주문의 주문 시점 상품명·수량·단가를 함께 제공합니다. 회원 탈퇴 후에도 사용자와 주문·결제 행을 삭제하지 않아 기존 구매내역을 보존합니다.

## 확인 방법

서버 실행 후 `http://127.0.0.1:8000/docs`에서 로그인한 뒤 위 경로를 호출합니다. 기본 테스트는 `C:\AI4`에서 다음 명령으로 실행할 수 있습니다.

```powershell
& 'C:\AI4\.venv\Scripts\python.exe' -m pytest -c .\Day12-Demo\project\pytest.ini .\Day12-Demo\project\tests -m "not integration" -q
```
