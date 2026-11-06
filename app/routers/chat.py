from flask import Blueprint, current_app, request
from uuid import UUID

from app.core.errors import HTTPException
from app.core.http import json_response, request_body, validate_value
from app.core.dependencies import get_current_user
from app.db.connection import get_connection
from app.schemas.chat import ChatRequest
from app.services import products
from app.services import chat_history
from app.services.chat import GroqChat


router = Blueprint("chat", __name__, url_prefix="/api/chat")


@router.get("/status")
def status():
    get_current_user()
    settings = current_app.config["settings"]
    configured = bool(settings.groq_api_key and settings.groq_api_key.get_secret_value().strip())
    # Reports configuration only; does not send a billable generation or expose the key.
    return json_response({"configured": configured, "model": settings.groq_model})


@router.post("")
def complete():
    user = get_current_user()
    if request.content_length is not None and request.content_length > 65536:
        raise HTTPException(413, "대화 내용이 너무 깁니다.")
    payload = request_body(ChatRequest)
    settings = current_app.config["settings"]
    if not settings.groq_api_key or not settings.groq_api_key.get_secret_value().strip():
        raise HTTPException(503, "AI 연결 설정이 필요합니다. 서버의 GROQ_API_KEY를 설정하세요.")
    connection = get_connection()
    messages = chat_history.prepare(connection, user['id'], payload)
    current_app.extensions["chat_limiter"].acquire(settings)
    catalog = products.list_products(connection, limit=30, offset=0)["items"]
    result = GroqChat(settings).complete(messages, catalog)
    result.update(chat_history.save_turn(connection, user['id'], payload, result))
    return json_response(result)


@router.get('/conversations')
def conversations():
    user = get_current_user()
    return json_response({'items': chat_history.list_conversations(get_connection(), user['id']), 'limit': 10})


@router.get('/conversations/<conversation_id>')
def conversation(conversation_id):
    user = get_current_user()
    conversation_id = validate_value(UUID, conversation_id, 'path.conversation_id')
    return json_response(chat_history.detail(get_connection(), user['id'], conversation_id))


@router.delete('/conversations/<conversation_id>')
def delete_conversation(conversation_id):
    user = get_current_user()
    conversation_id = validate_value(UUID, conversation_id, 'path.conversation_id')
    chat_history.delete(get_connection(), user['id'], conversation_id)
    return '', 204
