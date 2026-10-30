from urllib.parse import urlsplit

from flask import current_app, jsonify, request


def request_origin() -> str | None:
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


def enforce_same_origin():
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        expected = current_app.config["settings"].app_origin
        if (
            request.headers.get("sec-fetch-site") == "cross-site"
            or request_origin() != expected
        ):
            return (
                jsonify(
                    detail="요청 출처를 확인할 수 없습니다. 같은 사이트에서 다시 요청하세요."
                ),
                403,
            )
