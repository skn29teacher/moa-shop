"""User-owned conversation storage; never hold a SQLite write lock during inference."""
import json
from uuid import uuid4

from app.core.errors import HTTPException


LIMIT = 10


def list_conversations(connection, user_id):
    return connection.execute('''SELECT id,title,revision,created_at,updated_at FROM chat_conversations
        WHERE user_id=? ORDER BY updated_at DESC,id DESC''', (user_id,)).fetchall()


def owned(connection, user_id, conversation_id):
    row = connection.execute('SELECT * FROM chat_conversations WHERE id=? AND user_id=?',
                             (conversation_id, user_id)).fetchone()
    if row is None:
        raise HTTPException(404, '대화를 찾을 수 없습니다.')
    return row


def messages(connection, conversation_id, recent=False):
    sql = 'SELECT role,content,sources_json FROM chat_messages WHERE conversation_id=? ORDER BY sequence '
    rows = connection.execute(sql + ('DESC LIMIT 10' if recent else 'ASC'), (conversation_id,)).fetchall()
    if recent:
        rows.reverse()
    return [dict(role=row['role'], content=row['content'], sources=json.loads(row['sources_json'])) for row in rows]


def detail(connection, user_id, conversation_id):
    row = owned(connection, user_id, conversation_id)
    return {key: row[key] for key in ('id', 'title', 'revision', 'created_at', 'updated_at')} | {
        'messages': messages(connection, conversation_id)}


def prepare(connection, user_id, payload):
    if payload.conversation_id:
        row = owned(connection, user_id, payload.conversation_id)
        if row['revision'] != payload.revision:
            raise HTTPException(409, '다른 화면에서 대화가 변경됐습니다. 대화를 다시 열어 주세요.')
        previous = messages(connection, payload.conversation_id, recent=True)
    else:
        if len(list_conversations(connection, user_id)) >= LIMIT:
            raise HTTPException(409, '대화는 최대 10개까지 저장할 수 있습니다. 기존 대화를 삭제한 뒤 새 대화를 시작하세요.')
        previous = []
    prompt = payload.messages[-1].content
    while previous and sum(len(row['content']) for row in previous) + len(prompt) > 12000:
        del previous[:2]
    # Submitted assistant history is never trusted; load context from this user's DB instead.
    return [dict(role=row['role'], content=row['content']) for row in previous] + [{'role': 'user', 'content': prompt}]


def save_turn(connection, user_id, payload, result):
    with connection.transaction():
        user = connection.execute('SELECT id FROM users WHERE id=? AND deleted_at IS NULL', (user_id,)).fetchone()
        if user is None:
            raise HTTPException(401, '로그인이 필요합니다.')
        if payload.conversation_id:
            row = owned(connection, user_id, payload.conversation_id)
            if row['revision'] != payload.revision:
                raise HTTPException(409, '다른 화면에서 대화가 변경됐습니다. 대화를 다시 열어 주세요.')
            conversation_id, revision = payload.conversation_id, row['revision']
        else:
            if len(list_conversations(connection, user_id)) >= LIMIT:
                raise HTTPException(409, '대화는 최대 10개까지 저장할 수 있습니다. 기존 대화를 삭제해 주세요.')
            conversation_id, revision = uuid4(), 0
            connection.execute('INSERT INTO chat_conversations(id,user_id,title) VALUES (?,?,?)',
                               (conversation_id, user_id, payload.messages[-1].content[:60]))
        for sequence, role, content, sources in [
            (revision * 2 + 1, 'user', payload.messages[-1].content, []),
            (revision * 2 + 2, 'assistant', result['reply'], result.get('sources', [])),
        ]:
            connection.execute('''INSERT INTO chat_messages(conversation_id,sequence,role,content,sources_json)
                VALUES (?,?,?,?,?)''', (conversation_id, sequence, role, content, json.dumps(sources, ensure_ascii=False)))
        connection.execute("""UPDATE chat_conversations SET revision=revision+1,
            updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=? AND user_id=?""", (conversation_id, user_id))
    return {'conversation_id': str(conversation_id), 'revision': revision + 1}


def delete(connection, user_id, conversation_id):
    with connection.transaction():
        owned(connection, user_id, conversation_id)
        connection.execute('DELETE FROM chat_conversations WHERE id=? AND user_id=?', (conversation_id, user_id))
