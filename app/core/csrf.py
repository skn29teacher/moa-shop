from urllib.parse import urlsplit

from fastapi import Request
from starlette.responses import JSONResponse


def request_origin(request: Request) -> str | None:
    # Origin이 있으면 Referer로 우회하지 않습니다. Origin:null도 거부됩니다.
    origin = request.headers.get("origin")
    if origin is not None:
        return origin
    referer = request.headers.get("referer")
    if not referer:
        return None
    try:
        parsed = urlsplit(referer)
        return f"{parsed.scheme}://{parsed.netloc}"
    except ValueError:
        return None


async def enforce_same_origin(request: Request, call_next):
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        expected = request.app.state.settings.app_origin
        if (
            request.headers.get("sec-fetch-site") == "cross-site"
            or request_origin(request) != expected
        ):
            return JSONResponse(
                status_code=403,
                content={"detail": "요청 출처를 확인할 수 없습니다. 같은 사이트에서 다시 요청하세요."},
            )
    return await call_next(request)
