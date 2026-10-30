import logging
import sqlite3
from urllib.parse import urlsplit

from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException as WerkzeugHTTPException

from app.core.config import PROJECT_ROOT, Settings, get_settings
from app.core.csrf import enforce_same_origin
from app.core.errors import HTTPException, RequestValidationError
from app.core.http import json_response
from app.db.connection import close_connection, create_pool
from app.routers.auth import router as auth_router
from app.routers.admin import router as admin_router
from app.routers.cart import router as cart_router
from app.routers.members import router as members_router
from app.routers.orders import router as orders_router
from app.routers.payments import router as payments_router
from app.routers.products import router as products_router


logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, pool=None) -> Flask:
    settings = settings or get_settings()
    if not settings.supabase_url or not settings.supabase_key:
        raise RuntimeError("SUPABASE_URL과 SUPABASE_KEY(publishable 또는 anon)를 설정하세요.")
    auth_url = urlsplit(settings.supabase_url)
    if (auth_url.scheme != "https" or not auth_url.hostname or auth_url.path not in ("", "/")
            or auth_url.query or auth_url.fragment or auth_url.username or auth_url.password):
        raise RuntimeError("SUPABASE_URL은 경로가 없는 HTTPS 프로젝트 주소여야 합니다.")
    if pool is None:
        pool = create_pool(settings)
    try:
        pool.open(wait=True, timeout=10)
    except Exception as exc:
        pool.close()
        raise RuntimeError(
            "SQLite DB를 열거나 초기화하지 못했습니다. DATABASE_PATH, 파일 권한과 SQLite 버전을 확인하세요."
        ) from exc

    app = Flask(
        __name__,
        template_folder=str(PROJECT_ROOT / "templates"),
        static_folder=str(PROJECT_ROOT / "static"),
        static_url_path="/static",
    )
    app.config.update(settings=settings, db_pool=pool)
    from app.cli import register_commands
    register_commands(app)
    app.teardown_appcontext(close_connection)
    app.before_request(enforce_same_origin)
    app.register_blueprint(auth_router)
    app.register_blueprint(admin_router)
    app.register_blueprint(products_router)
    app.register_blueprint(cart_router)
    app.register_blueprint(orders_router)
    app.register_blueprint(payments_router)
    app.register_blueprint(members_router)

    @app.get("/")
    @app.get("/auth/confirm")
    def home_page():
        return render_template("index.html")

    @app.after_request
    def prevent_api_caching(response):
        if request.path.startswith("/api/") or request.path == "/auth/confirm":
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(RequestValidationError)
    def validation_error_handler(exc: RequestValidationError):
        return jsonify(
            detail="입력값을 확인하세요.",
            errors=exc.errors,
        ), 422

    @app.errorhandler(HTTPException)
    def api_error_handler(exc: HTTPException):
        return jsonify(detail=exc.detail), exc.status_code

    @app.errorhandler(sqlite3.OperationalError)
    def database_unavailable_handler(_exc: Exception):
        logger.error("데이터베이스 연결을 사용할 수 없습니다.")
        return jsonify(detail="DB 연결을 사용할 수 없습니다. 잠시 후 다시 시도하세요."), 503

    @app.errorhandler(WerkzeugHTTPException)
    def http_error_handler(exc: WerkzeugHTTPException):
        return jsonify(detail=exc.description), exc.code

    return app
