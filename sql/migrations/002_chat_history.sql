-- Additive migration: existing shop data and sessions are preserved.
CREATE TABLE chat_conversations (
    id TEXT PRIMARY KEY NOT NULL,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL CHECK (length(title) BETWEEN 1 AND 60),
    revision INTEGER NOT NULL DEFAULT 0 CHECK (revision >= 0),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX chat_conversations_user_idx ON chat_conversations(user_id, updated_at DESC);
CREATE TRIGGER chat_conversations_limit BEFORE INSERT ON chat_conversations
WHEN (SELECT count(*) FROM chat_conversations WHERE user_id = NEW.user_id) >= 10
BEGIN
    SELECT RAISE(ABORT, 'chat_conversation_limit');
END;
CREATE TABLE chat_messages (
    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL REFERENCES chat_conversations(id) ON DELETE CASCADE,
    sequence INTEGER NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL CHECK (length(content) BETWEEN 1 AND 4000),
    sources_json TEXT NOT NULL DEFAULT '[]',
    UNIQUE (conversation_id, sequence)
);
CREATE TRIGGER chat_history_delete_on_member AFTER UPDATE OF deleted_at ON users
WHEN NEW.deleted_at IS NOT NULL
BEGIN
    DELETE FROM chat_conversations WHERE user_id = NEW.id;
END;
