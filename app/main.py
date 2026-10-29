import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from psycopg import OperationalError
from psycopg_pool import PoolTimeout
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse

from app.core.config import PROJECT_ROOT, get_settings
from app.core.csrf import enforce_same_origin
from app.db.connection import create_pool
from app.routers.auth import router as auth_router
from app.routers.cart import router as cart_router
from app.routers.orders import router as orders_router
from app.routers.payments import router as payments_router
from app.routers.products import router as products_router
from app.routers.members import router as members_router


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings
    pool = create_pool(settings)
    app.state.db_pool = pool
    try:
        # 접속 확인은 사용자가 서버를 시작할 때 수행됩니다.
        await run_in_threadpool(pool.open, wait=True, timeout=10)
    except Exception:
        await run_in_threadpool(pool.close)
        raise RuntimeError(
            "DB 연결을 시작하지 못했습니다. .env의 DATABASE_URL과 Supabase 연결 상태를 확인하세요."
        ) from None
    try:
        yield
    finally:
        await run_in_threadpool(pool.close)


app = FastAPI(title="쇼핑몰 MVP", version="0.2.0", lifespan=lifespan)
app.middleware("http")(enforce_same_origin)
app.include_router(auth_router)
app.include_router(products_router)
app.include_router(cart_router)
app.include_router(orders_router)
app.include_router(payments_router)
app.include_router(members_router)
# HTML/CSS/JS는 FastAPI가 직접 서빙합니다. 경로는 실행 위치에 의존하지 않습니다.
app.mount("/static", StaticFiles(directory=PROJECT_ROOT / "static"), name="static")


@app.get("/", include_in_schema=False)
def home_page():
    return FileResponse(PROJECT_ROOT / "templates" / "index.html")


@app.middleware("http")
async def prevent_api_caching(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    # 기본 검증 오류에 포함될 수 있는 비밀번호 원문(input)을 응답에서 제거합니다.
    return JSONResponse(
        status_code=422,
        content={
            "detail": "입력값을 확인하세요.",
            "errors": [
                {"field": list(error["loc"]), "message": error["msg"], "type": error["type"]}
                for error in exc.errors()
            ],
        },
    )


@app.exception_handler(OperationalError)
@app.exception_handler(PoolTimeout)
async def database_unavailable_handler(request: Request, exc: Exception):
    # 접속 문자열·DB 내부 오류는 브라우저 응답이나 로그에 출력하지 않습니다.
    logger.error("데이터베이스 연결을 사용할 수 없습니다.")
    return JSONResponse(status_code=503, content={"detail": "DB 연결을 사용할 수 없습니다. 잠시 후 다시 시도하세요."})
