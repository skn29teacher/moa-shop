# Groq 무료 API 채팅: 가입부터 로컬 테스트와 PythonAnywhere 배포까지

기준일: 2026-11-06. 현재 프로젝트는 Flask에서 Groq HTTPS API를 호출하고, 공개 상품과 등록 문서를 근거 자료로 제공합니다. 로컬과 PythonAnywhere 무료 배포에 같은 코드를 사용합니다. 모델 파일·GPU·Groq SDK가 필요하지 않습니다. Python 표준 라이브러리 `urllib.request`를 사용하므로 기존 `requirements.txt`로 실행합니다. 실제 배포 서버의 연결 성공 여부는 배포 후 점검 명령으로 확인합니다.

```text
브라우저 /#/chat → Flask POST /api/chat → 공개 상품 조회·knowledge 문서 검색 → Groq → 채팅 화면
```

## 1. Groq 가입 및 API 키 발급

1. [Groq Console](https://console.groq.com/)을 열고 계정을 생성하거나 로그인합니다. 제공되는 로그인 방식 중 하나를 선택하고 화면에서 요구하는 이메일 확인·조직 설정을 완료합니다.
2. [API Keys](https://console.groq.com/keys)에서 **Create API Key**를 선택합니다. 이름은 `moashop-local`처럼 목적을 구분해 입력합니다. 만료 옵션이 있으면 필요한 기간을 선택합니다.
3. 발급된 키를 비밀 저장소 또는 아래 로컬 `.env`에 보관합니다. 키 전체를 채팅·스크린샷·Git·HTML·JavaScript에 넣지 않습니다. 노출했다면 해당 키를 폐기하고 재발급합니다.
4. 무료로 이용하려면 Free 플랜을 유지합니다. 유료 Developer 업그레이드는 이번 구성에 필요하지 않습니다. [Billing](https://console.groq.com/settings/billing)에서 현재 플랜을 확인합니다.
5. [Limits](https://console.groq.com/settings/limits)와 [Models](https://console.groq.com/docs/models)에서 계정에서 사용할 수 있는 모델과 한도를 확인합니다. 코드의 기본 모델은 `openai/gpt-oss-20b`입니다. 사용할 수 없다면 `.env`의 `GROQ_MODEL`에 계정에 허용된 Chat Completions 모델 ID를 설정합니다. Hugging Face 모델 ID를 임의로 넣어 사용할 수는 없습니다.

로컬과 배포 환경은 키를 별도로 발급하면 폐기·교체하기 쉽습니다. 같은 Groq 조직에 속하면 키를 나눠도 사용 한도는 공유됩니다. 무료 한도·모델 제공 여부는 변경될 수 있으므로 콘솔을 기준으로 확인합니다. [Groq 공식 시작 안내](https://console.groq.com/docs/quickstart), [사용 제한](https://console.groq.com/docs/rate-limits), [요금 안내](https://console.groq.com/docs/billing-faqs).

## 2. 로컬 설정 — Windows PowerShell

프로젝트 위치로 이동하고 의존성을 설치합니다. 가상환경이 이미 있으면 재사용합니다.

```powershell
Set-Location 'C:\AI4\Day12-Demo\project'
if (-not (Test-Path -LiteralPath '.\.venv\Scripts\python.exe')) {
    python -m venv .venv
}
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path -LiteralPath '.\.env')) {
    Copy-Item -LiteralPath '.\.env.example' -Destination '.\.env'
}
notepad .env
```

`.env`의 기존 Supabase·SECRET_KEY·DB 설정은 유지하고 다음 항목을 추가하거나 수정합니다. 아래 키 자리는 실제 발급 키로 바꾸되, 기존 파일 전체를 예시로 덮어쓰지 않습니다.

```dotenv
GROQ_API_KEY=여기에_본인의_실제_API_키
GROQ_MODEL=openai/gpt-oss-20b
GROQ_TIMEOUT_SECONDS=25
GROQ_MAX_COMPLETION_TOKENS=1024
CHAT_REQUESTS_PER_MINUTE=10
CHAT_REQUESTS_PER_DAY=100
```

로컬 HTTP 설정은 아래와 같습니다. 브라우저에서도 `localhost` 대신 같은 `127.0.0.1` 주소를 사용합니다.

```dotenv
APP_ORIGIN=http://127.0.0.1:8000
COOKIE_SECURE=false
```

`.env`는 프로젝트 설정이 자동으로 읽습니다. 운영체제에 같은 이름의 환경변수가 있으면 그 값이 우선하므로 예전 값을 확인합니다. `.env` 수정 후 실행 중인 Flask를 종료하고 다시 실행해야 합니다. 실제 키를 명령행 인자로 전달하지 않습니다.

이 앱은 기존 쇼핑몰 설정인 `SUPABASE_URL`, `SUPABASE_KEY`, 32자 이상의 유효한 `SECRET_KEY`도 필요합니다. 처음 설치라면 [로컬 환경 가이드](LOCAL_TESTING.md)를 함께 따릅니다. Groq 키가 비어 있어도 쇼핑몰과 대화 예시를 이용할 수 있으며, 실제 채팅 전송은 비활성화됩니다.

## 3. 키·모델·실제 응답 확인

키와 선택한 모델을 확인합니다. 이 명령은 모델 목록을 조회하며 채팅을 생성하지 않습니다. 키 값은 출력하지 않습니다.

```powershell
.\.venv\Scripts\python.exe -m flask --app wsgi:application check-groq
```

예상 성공 출력:

```text
Groq HTTPS 연결 및 모델 확인 성공: openai/gpt-oss-20b
```

실제 생성까지 확인하려면 다음 명령을 실행합니다. 고정된 한국어 인사 질문 1건을 Groq로 전송하며 사용 한도를 소비합니다. 테스트 문장 외의 회원·주문 정보는 전송하지 않습니다.

```powershell
.\.venv\Scripts\python.exe -m flask --app wsgi:application check-groq --generate
```

모델 목록 조회 성공은 해당 모델의 무료 생성 가능 여부나 남은 할당량까지 보장하지 않습니다. `--generate`와 콘솔 Limits를 함께 확인합니다.

## 4. 서버 실행 및 화면 테스트

```powershell
.\.venv\Scripts\python.exe -m flask --app wsgi:application run --debug --no-reload --host 127.0.0.1 --port 8000
```

이미 8000 포트의 서버가 실행 중이면 기존 서버에서 Ctrl+C로 종료한 뒤 재시작합니다. [AI 쇼핑 도우미](http://127.0.0.1:8000/#/chat)를 열고, 필요하면 Ctrl+F5로 새 코드를 반영합니다.

- 상단 **Groq · 연결 설정됨**은 키가 설정되었다는 뜻입니다. 키 유효성·외부 접속·할당량은 실제 전송이나 `check-groq`로 확인합니다.
- 추천 질문을 누른 뒤 전송 버튼 또는 Enter로 보냅니다. Shift+Enter는 줄바꿈입니다.
- 응답 대기 중에는 중복 전송을 막습니다. 오류가 나면 질문이 입력창에 남아 재시도할 수 있습니다.
- **새로운 대화**를 누르면 현재 화면의 대화가 초기화됩니다. 브라우저 화면을 이동하거나 새로고침해도 초기화됩니다.
- **대화 예시**는 가상 대화이며 Groq를 호출하지 않습니다. 첨부 기능은 아직 제공하지 않습니다.

확인할 질문 예시:

```text
현재 판매하는 가방의 가격과 재고를 알려줘.
그 상품은 2만 원 예산에 맞아?
내 주문은 어디에서 확인할 수 있어?
```

공개 상품 목록의 최대 30개를 매 요청 시 DB에서 읽어 모델에 제공합니다. `knowledge/`의 UTF-8 `.md`·`.txt` 문서에서도 질문과 관련된 구간을 찾아 함께 제공합니다. 문서 등록 방법·제한·출처 표시는 [문서 폴더 안내](../knowledge/README.md)를 참고하세요. 회원정보·주소·주문 내역은 제공하지 않습니다. 실제 주문 조회나 상품 담기·결제는 실행하지 않습니다. AI가 제공된 정보와 다르게 답할 수 있으므로 최종 상품 화면을 확인합니다.

문서 등록·검색 확인 명령 (Groq 호출 없음):

```powershell
$env:PYTHONIOENCODING='utf-8'
.\.venv\Scripts\python.exe -m flask --app wsgi:application check-chat-docs
.\.venv\Scripts\python.exe -m flask --app wsgi:application check-chat-docs --query '환불'
```

## 5. PowerShell에서 API 직접 테스트

Flask가 켜진 상태에서 새 PowerShell 창을 열어 실행합니다. API 키는 브라우저나 이 요청 본문에 필요하지 않습니다. 서버의 `.env`에서만 읽습니다.

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/chat/status'
$chatTestBody = @{
    messages = @(@{ role = 'user'; content = '판매 중인 가방을 소개해 줘.' })
} | ConvertTo-Json -Depth 5
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/api/chat' `
    -Headers @{ Origin = 'http://127.0.0.1:8000' } `
    -ContentType 'application/json; charset=utf-8' `
    -Body ([System.Text.Encoding]::UTF8.GetBytes($chatTestBody))
```

성공하면 `reply`, `model`, `sources`가 반환됩니다. `sources`는 모델에 전달한 검색 문서의 메타데이터이며 관련 문서가 없으면 빈 배열입니다. 본문이나 서버 절대 경로는 포함하지 않습니다. 예를 들어 기본 안내를 검색하면 다음과 같은 항목이 반환됩니다.

```json
{
  "id": "문서1",
  "file": "shop-guide.md",
  "start_line": 1,
  "end_line": 16
}
```

화면은 이 목록을 '검색된 참고 문서'로 표시합니다. 모델에는 근거 문장 뒤에 `[문서1]` 같은 ID를 쓰도록 지시하지만 모든 문장의 정확성과 인용을 서버가 검증하는 것은 아닙니다. 변경 요청의 `Origin`은 서버 `APP_ORIGIN`과 같아야 합니다. API 클라이언트에서 Origin을 생략하면 403입니다.

## 6. API 키 없이 자동 테스트

아래 테스트는 외부 Groq를 호출하지 않으며 무료 할당량을 사용하지 않습니다. 응답 대역을 사용해 입력 검증, 서버 시스템 프롬프트, 공개 상품 문맥, 키 누출 방지, 잘못된 키·한도·타임아웃·빈 응답·요청 제한과 CLI를 확인합니다.

```powershell
Set-Location 'C:\AI4\Day12-Demo\project'
.\.venv\Scripts\python.exe -m pip install -r requirements-test.txt
.\.venv\Scripts\python.exe -m pytest tests/test_chat.py tests/test_knowledge.py -q -p no:cacheprovider
node --check static/js/chat-preview.js
node --test tests/chat-markdown.test.cjs
```

전체 회귀 테스트:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
node --test tests/auth-confirmation.test.cjs tests/chat-markdown.test.cjs
```

Windows 임시 폴더의 권한 오류가 나면 접근 가능한 고유한 테스트 폴더를 지정합니다. `--basetemp`는 해당 폴더를 비우므로 아래처럼 새 GUID 폴더를 사용합니다.

```powershell
$chatTestTemp = Join-Path (Get-Location) ('.test-runs/groq-' + [guid]::NewGuid().ToString('N'))
.\.venv\Scripts\python.exe -m pytest tests/test_chat.py tests/test_knowledge.py -q -p no:cacheprovider --basetemp $chatTestTemp
```

## 7. PythonAnywhere 무료 배포

문서 검색 업데이트에는 `app/services/knowledge.py`와 프로젝트 루트의 `knowledge/` 폴더도 포함합니다. 등록 문서는 Groq로 전송되므로 공개 안내만 넣습니다. 업로드 뒤 `check-chat-docs --query '환불'`로 검색을 확인하고 최초 코드 변경 시 Web Reload를 합니다.

기존 [배포 가이드](DEPLOYMENT.md)의 경로·가상환경을 재사용합니다. 아래는 현재 문서의 계정명 기준이며 다른 계정이면 경로를 바꿉니다.

매 배포 전에 내 PC의 PowerShell에서 아래 명령으로 최신 소스를 압축합니다. `dist/moashop-sqlite-deploy.zip`을 PythonAnywhere **Files → /home/kyuyounglee → Upload a file**에서 선택합니다. ZIP 구성과 서버 압축 해제 명령은 [배포 문서](DEPLOYMENT.md#2-2-올릴-파일과-zip-내부-구조)를 참고하세요.

```powershell
Set-Location 'C:\AI4\Day12-Demo\project'
.\.venv\Scripts\python.exe scripts/package_deploy.py
```

1. 변경한 `app/`, `templates/`, `static/` 등 소스를 업로드합니다. 서버의 실제 `.env`, SQLite DB를 로컬 파일로 덮어쓰지 않습니다. 새 파일 `app/routers/chat.py`, `app/services/chat.py`, `app/schemas/chat.py`, `static/js/chat-preview.js`, `static/js/chat-markdown.js`, `static/css/chat.css`, `static/vendor/markdown-it/`도 포함해야 합니다. 마크다운 라이브러리는 프로젝트에 포함되어 별도 npm 설치나 외부 CDN 접속이 필요하지 않습니다.
2. 서버 `/home/kyuyounglee/moashop/.env`에 위 Groq 설정을 추가합니다. 실제 키는 Files 편집기에서 입력하고 저장합니다.
3. 운영 환경의 기존 설정을 유지합니다.

```dotenv
APP_ORIGIN=https://kyuyounglee.pythonanywhere.com
COOKIE_SECURE=true
```

4. Bash 콘솔에서 환경을 활성화하고 확인합니다.

```bash
cd /home/kyuyounglee/moashop
source /home/kyuyounglee/.virtualenvs/moashop-sqlite/bin/activate
python -m pip install -r requirements.txt
python -m flask --app wsgi:application check-groq
python -m flask --app wsgi:application check-groq --generate
```

5. **Web → Reload** 후 `https://kyuyounglee.pythonanywhere.com/#/chat`에서 질문을 전송합니다. PythonAnywhere에서는 `flask run`을 별도로 띄우지 않고 기존 WSGI 앱을 사용합니다.

무료 계정의 `api.groq.com` HTTPS 접속은 [허용 목록](https://www.pythonanywhere.com/whitelist/)에 포함되어 있습니다. 클라이언트는 `urllib.request`의 기본 프록시 환경변수를 사용합니다. 기본 환경에서 실패하면 먼저 [공식 프록시 안내](https://help.pythonanywhere.com/pages/403ForbiddenError/)를 확인합니다.

환경변수가 누락된 경우 **PythonAnywhere에서만** 다음을 `.env`에 추가합니다. 로컬 Windows `.env`에는 넣지 않습니다. 설정 변경 뒤 콘솔 재실행과 Web Reload를 합니다.

```dotenv
HTTPS_PROXY=http://proxy.server:3128
HTTP_PROXY=http://proxy.server:3128
```

추가 항목을 `.env`에서 프로세스 환경으로 옮겨야 한다면 WSGI 파일의 `from wsgi import application` **앞**에 아래를 추가합니다. `python-dotenv`는 기존 `pydantic-settings`의 의존성입니다. 이 작업은 프로세스 환경에 프록시를 반영하기 위한 것입니다.

```python
from dotenv import load_dotenv
load_dotenv('/home/kyuyounglee/moashop/.env', override=False)
```

## 8. 제한과 오류 해결

| 증상 | 확인할 내용 |
| --- | --- |
| API 키 설정 필요 / 503 | `.env`의 `GROQ_API_KEY`, Flask 재시작·Web Reload |
| 인증 또는 접근 설정 오류 | 키 폐기·만료·조직 권한, PythonAnywhere 프록시, 콘솔 접근 설정 |
| 모델 설정 오류 | 실제 사용 가능한 모델 ID, `check-groq`, 콘솔 모델 권한 |
| 429 | Groq 무료 요청·토큰 한도 또는 앱의 데모 요청 제한; 반복 재시도하지 말고 대기 |
| 연결 지연 / 503 | 인터넷·프록시·Groq 상태; 기본 서버 타임아웃 25초 |
| 빈 답변 / 502 | 다시 시도; 추론 모델이라면 출력 토큰 한도를 조정하거나 다른 허용 모델 선택 |
| Origin 관련 403 | `APP_ORIGIN`과 브라우저 도메인·포트 일치 여부 |
| 422 | 질문 2,000자 이하, user/assistant 교대, 마지막 user, 전체 문맥 12,000자 이하 |
| 이전 미리보기 화면 | 변경한 JS·CSS·템플릿 업로드, Web Reload, Ctrl+F5 |
| 참고 문서를 찾지 못함 | knowledge 업로드·확장자·UTF-8·용량·질문 키워드와 check-chat-docs 결과 확인 |
| 환불 정책을 답하지 않음 | 현재 환불 정책은 작성 예시만 제공; 실제 승인 문서를 등록해야 함 |
| Windows 출력 중 UnicodeEncodeError | PowerShell에서 $env:PYTHONIOENCODING='utf-8' 설정 후 재실행 |

- 대화는 브라우저 화면 메모리에만 유지하고 DB·localStorage에 저장하지 않습니다. 요청에는 최근 최대 5쌍의 대화와 현재 질문을 포함하며, 전체 문자 제한에 맞춰 오래된 쌍부터 제외합니다.
- 질문·최근 대화·공개 상품 정보·검색된 참고 문서 구간은 Groq로 전송됩니다. 모델 제공자의 처리 정책은 [Groq Your Data](https://console.groq.com/docs/your-data)를 확인합니다. 개인정보를 입력하거나 참고 문서에 넣지 않습니다.
- AI 답변은 마크다운 표·목록·제목·강조·링크·코드 블록으로 렌더링합니다. 넓은 표는 가로 스크롤할 수 있습니다. 원시 HTML은 이스케이프하고 위험 URL과 외부 이미지 로딩을 차단합니다. 사용자 입력은 일반 텍스트로 표시하며 추론 내부 내용은 표시하지 않습니다.
- 앱 제한은 기본 **전체 방문자 합계, 워커당 분당 10건·최근 24시간 100건**입니다. 실패한 시도도 포함하며 프로세스 재시작 시 초기화됩니다. 여러 워커에서는 각각 별도 카운터이므로 영구 사용량·비용 제한이 아닙니다. CLI 점검은 이 카운터를 거치지 않습니다.
- 공개 시연을 위한 동기식 비스트리밍 채팅입니다. 로그인 없이 호출할 수 있으며 사용자별 인증·영속적 사용량 제한은 구현하지 않았습니다. Origin 검사는 인증 수단이 아니므로 공개 서비스의 악용 방지 수단을 대체하지 않습니다.
- 실제 연결 성공은 본인 계정의 `check-groq --generate`와 화면 전송으로 검증합니다. 자동 테스트 통과를 실제 Groq 계정 인증 성공으로 해석하지 않습니다.

## 9. 지시문과 참고 문서 관리

| 바꾸려는 내용 | 수정 위치 | 반영 시점 |
| --- | --- | --- |
| AI 역할·말투·답변 범위·금지 사항 | `app/services/chat.py`의 `SYSTEM_PROMPT` | Flask 재시작 / PythonAnywhere Web Reload |
| 환불·배송·FAQ 등 공개 사실 | `knowledge/`의 승인된 `.md`·`.txt` | 다음 질문부터 다시 읽음 |
| 검색 방식·파일 및 구간 제한 | `app/services/knowledge.py` | 코드 재시작 / Reload |
| 모델·타임아웃·출력량·요청 한도 | 서버 `.env`의 Groq·CHAT 설정 | 코드 재시작 / Reload |

상품 목록은 모아샵 DB에서 조회한 공개 상품 정보이며 상품명 등의 문장을 행동 지시로 따르지 않도록 명시했습니다. 정책 문서에도 같은 규칙을 적용합니다. 문서에 없는 환불 기간·비용·문의처를 학습 지식이나 과거 대화로 만들어내지 않도록 지시합니다. DB 가격·재고가 우선이고, 문서 충돌 시 운영 확인이 필요하다고 안내하도록 지시합니다.

등록 문서가 있으면 질문 단어·한국어 두 글자 조합으로 관련 구간을 검색합니다. 최근 사용자 질문은 후속 질문을 보완하고 이전 AI 답변은 검색 근거로 사용하지 않습니다. 이 방식은 임베딩 기반 의미 검색이 아니므로 동의어나 모호한 표현을 놓칠 수 있습니다. 검색되는지 `check-chat-docs --query`로 확인하고 파일 제목·본문에 실제 질문에 쓰이는 단어를 포함하세요.

기본 등록 문서는 `knowledge/shop-guide.md`입니다. 환불 정책 작성 틀 `refund-policy.md.example`과 `knowledge/README.md`는 모델에 전달하지 않습니다. 정책을 확정해 UTF-8 `refund-policy.md`로 등록하기 전까지 환불 검색 결과가 0개인 것은 정상입니다. 일반 `docs/`를 수정해도 AI 참고 정책이 바뀌지 않습니다. 문서 본문은 공개 URL로 제공하지 않지만 관련 구간이 Groq로 전송되므로 비밀·개인정보를 넣지 않습니다.

문서당 128KiB·전체 1MiB·최대 50개, 구간 약 1,200자·최대 4개를 사용합니다. 숨김 경로·심볼릭 링크·지원하지 않는 확장자를 제외하고, UTF-8·용량 문제는 점검 명령에 표시합니다. 자세한 등록·제외 규칙은 [문서 폴더 안내](../knowledge/README.md)에 있습니다.

문서 수정 후에는 '새로운 대화'에서 정책 질문을 다시 시험하세요. 프롬프트와 검색된 자료를 제공하는 구조이며 엄격한 사실 검증이나 모든 지시문 공격 차단을 보장하지 않습니다. 테스트 결과와 실제 모델 호출 확인의 범위는 [로컬 테스트 문서](LOCAL_TESTING.md)에 기록합니다.
