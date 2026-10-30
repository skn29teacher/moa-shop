class HTTPException(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class RequestValidationError(Exception):
    def __init__(self, errors: list[dict]):
        super().__init__("요청 입력값이 유효하지 않습니다.")
        self.errors = errors
