from flask import Blueprint, current_app, request

from app.core.errors import HTTPException
from app.core.http import json_response, request_body
from app.db.connection import get_connection
from app.schemas.chat import ChatRequest
from app.services import products
from app.services.chat import GroqChat


router = Blueprint("chat", __name__, url_prefix="/api/chat")


@router.get("/status")
def status():
    settings = current_app.config["settings"]
    configured = bool(settings.groq_api_key and settings.groq_api_key.get_secret_value().strip())
    # Reports configuration only; does not send a billable generation or expose the key.
    return json_response({"configured": configured, "model": settings.groq_model})


@router.post("")
def complete():
    if request.content_length is not None and request.content_length > 65536:
        raise HTTPException(413, "대화 내용이 너무 깁니다.")
    payload = request_body(ChatRequest)
    settings = current_app.config["settings"]
    if not settings.groq_api_key or not settings.groq_api_key.get_secret_value().strip():
        raise HTTPException(503, "AI 연결 설정이 필요합니다. 서버의 GROQ_API_KEY를 설정하세요.")
    current_app.extensions["chat_limiter"].acquire(settings)
    catalog = products.list_products(get_connection(), limit=30, offset=0)["items"]
    return json_response(GroqChat(settings).complete(
        [message.model_dump() for message in payload.messages], catalog))
