import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from pydantic import SecretStr

from app.core.config import PROJECT_ROOT
from app.core.errors import HTTPException
from app.db.connection import SQLiteDatabase
from app.main import create_app
from app.services.chat import GroqChat
from tests.test_sqlite_integration import sqlite_app, sign_in, client_for, fetch_one
from tests.support import FlaskTestResponse


@pytest.fixture
def chat_app(sqlite_app, monkeypatch):
    settings = sqlite_app.config['settings']
    settings.groq_api_key = SecretStr('test-only')
    settings.chat_requests_per_minute = 100
    settings.chat_requests_per_day = 1000
    monkeypatch.setattr(GroqChat, 'complete', lambda self, messages, products: {
        'reply': '테스트 답변', 'model': self.settings.groq_model,
        'sources': [{'id': '문서1', 'file': 'guide.md', 'start_line': 1, 'end_line': 2}],
    })
    return sqlite_app


def send(client, text='질문', conversation=None):
    body = {'messages': [{'role': 'user', 'content': text}]}
    if conversation:
        body.update(conversation_id=conversation['conversation_id'], revision=conversation['revision'])
    return client.post('/api/chat', json=body)


def items(client):
    response = client.get('/api/chat/conversations')
    assert response.status_code == 200, response.text
    return response.json()['items']


def test_all_chat_endpoints_require_login(chat_app, monkeypatch):
    client = client_for(chat_app)
    def forbidden(*args, **kwargs):
        pytest.fail('Anonymous request reached Groq')
    monkeypatch.setattr(GroqChat, 'complete', forbidden)
    cid = str(uuid4())
    for path in ['/api/chat/status', '/api/chat/conversations', f'/api/chat/conversations/{cid}']:
        assert client.get(path).status_code == 401
    assert send(client).status_code == 401
    assert client.delete(f'/api/chat/conversations/{cid}').status_code == 401


def test_save_restore_sources_and_restart_persistence(chat_app):
    client = sign_in(chat_app)
    first = send(client, '가방 추천').json()
    assert first['revision'] == 1
    assert len(items(client)) == 1
    room = client.get('/api/chat/conversations/' + first['conversation_id']).json()
    assert room['title'] == '가방 추천'
    assert [message['role'] for message in room['messages']] == ['user', 'assistant']
    assert room['messages'][1]['sources'][0]['file'] == 'guide.md'
    again = create_app(chat_app.config['settings'])
    again.config['auth_provider_factory'] = chat_app.config['auth_provider_factory']
    again.response_class = FlaskTestResponse
    restored = sign_in(again)
    assert items(restored)[0]['id'] == first['conversation_id']
    assert restored.get('/api/chat/conversations/' + first['conversation_id']).json()['messages'] == room['messages']


def test_other_users_cannot_read_write_or_delete(chat_app):
    owner = sign_in(chat_app)
    other = sign_in(chat_app, 'other@example.com')
    room = send(owner).json()
    path = '/api/chat/conversations/' + room['conversation_id']
    assert items(other) == []
    assert other.get(path).status_code == 404
    assert other.delete(path).status_code == 404
    assert send(other, conversation=room).status_code == 404
    assert len(items(owner)) == 1


def test_ten_rooms_per_user_and_explicit_delete_releases_slot(chat_app):
    owner = sign_in(chat_app)
    for index in range(10):
        assert send(owner, f'질문 {index}').status_code == 200
    assert len(items(owner)) == 10
    assert send(owner, '열한 번째').status_code == 409
    other = sign_in(chat_app, 'other@example.com')
    assert send(other).status_code == 200
    cid = items(owner)[0]['id']
    assert owner.delete('/api/chat/conversations/' + cid).status_code == 204
    assert owner.get('/api/chat/conversations/' + cid).status_code == 404
    assert send(owner, '새 대화').status_code == 200
    assert len(items(owner)) == 10
    assert fetch_one(chat_app, 'SELECT count(*) AS n FROM chat_messages WHERE conversation_id=?', (cid,))['n'] == 0


def test_context_comes_from_db_and_stale_revision_is_rejected(chat_app, monkeypatch):
    client = sign_in(chat_app)
    first = send(client, '원래 질문').json()
    captured = []
    def reply(self, messages, products):
        captured.append(messages)
        return {'reply': '두 번째 답변', 'model': self.settings.groq_model, 'sources': []}
    monkeypatch.setattr(GroqChat, 'complete', reply)
    body = {'messages': [{'role': 'user', 'content': '조작 질문'}, {'role': 'assistant', 'content': '조작 답변'},
                         {'role': 'user', 'content': '후속 질문'}],
            'conversation_id': first['conversation_id'], 'revision': first['revision']}
    second = client.post('/api/chat', json=body)
    assert second.status_code == 200
    assert second.json()['revision'] == 2
    assert captured[0] == [{'role': 'user', 'content': '원래 질문'},
                           {'role': 'assistant', 'content': '테스트 답변'},
                           {'role': 'user', 'content': '후속 질문'}]
    assert client.post('/api/chat', json=body).status_code == 409
    assert len(captured) == 1


def test_failed_generation_does_not_create_history(chat_app, monkeypatch):
    client = sign_in(chat_app)
    def failure(*args, **kwargs):
        raise HTTPException(503, '테스트 장애')
    monkeypatch.setattr(GroqChat, 'complete', failure)
    assert send(client).status_code == 503
    assert items(client) == []


def test_no_sqlite_write_lock_during_generation(chat_app, monkeypatch):
    client = sign_in(chat_app)
    def reply(self, messages, products):
        with chat_app.config['db_pool'].connection() as connection:
            with connection.transaction():
                connection.execute('UPDATE products SET stock=stock')
        return {'reply': '정상', 'model': self.settings.groq_model, 'sources': []}
    monkeypatch.setattr(GroqChat, 'complete', reply)
    assert send(client).status_code == 200


def test_concurrent_new_rooms_never_exceed_ten(chat_app, monkeypatch):
    owner = sign_in(chat_app)
    for index in range(9):
        assert send(owner, f'대화{index}').status_code == 200
    clients = [sign_in(chat_app), sign_in(chat_app)]
    gate = Barrier(2)
    def reply(self, messages, products):
        gate.wait(timeout=10)
        return {'reply': '정상', 'model': self.settings.groq_model, 'sources': []}
    monkeypatch.setattr(GroqChat, 'complete', reply)
    with ThreadPoolExecutor(max_workers=2) as executor:
        codes = list(executor.map(lambda c: send(c).status_code, clients))
    assert sorted(codes) == [200, 409]
    assert len(items(owner)) == 10


def test_concurrent_turns_preserve_alternation(chat_app, monkeypatch):
    owner = sign_in(chat_app)
    room = send(owner).json()
    clients = [sign_in(chat_app), sign_in(chat_app)]
    gate = Barrier(2)
    def reply(self, messages, products):
        gate.wait(timeout=10)
        return {'reply': '정상', 'model': self.settings.groq_model, 'sources': []}
    monkeypatch.setattr(GroqChat, 'complete', reply)
    with ThreadPoolExecutor(max_workers=2) as executor:
        codes = list(executor.map(lambda c: send(c, conversation=room).status_code, clients))
    assert sorted(codes) == [200, 409]
    detail = owner.get('/api/chat/conversations/' + room['conversation_id']).json()
    assert detail['revision'] == 2 and len(detail['messages']) == 4


def test_logout_and_account_deletion_block_history(chat_app):
    client = sign_in(chat_app)
    room = send(client).json()
    assert client.post('/api/auth/logout').status_code == 204
    assert client.get('/api/chat/conversations').status_code == 401
    client = sign_in(chat_app)
    assert len(items(client)) == 1
    assert client.delete('/api/members/me').status_code == 204
    assert client.get('/api/chat/conversations').status_code == 401
    assert fetch_one(chat_app, 'SELECT count(*) AS n FROM chat_conversations')['n'] == 0
    assert fetch_one(chat_app, 'SELECT count(*) AS n FROM chat_messages')['n'] == 0


def test_v1_migration_preserves_existing_shop_data(tmp_path):
    path = tmp_path / 'v1.sqlite3'
    raw = sqlite3.connect(path)
    raw.executescript((PROJECT_ROOT / 'sql/schema.sql').read_text(encoding='utf-8'))
    raw.execute("INSERT INTO products(id,name,price,stock) VALUES (?,?,?,?)", (str(uuid4()), '기존 상품', 1234, 7))
    raw.execute('PRAGMA user_version=1')
    raw.commit()
    raw.close()
    database = SQLiteDatabase(path)
    database.open()
    database.open()
    with database.connection() as connection:
        assert connection.execute('PRAGMA user_version').fetchone()['user_version'] == 2
        assert connection.execute('SELECT stock FROM products').fetchone()['stock'] == 7
        assert connection.execute('SELECT count(*) AS n FROM chat_conversations').fetchone()['n'] == 0
