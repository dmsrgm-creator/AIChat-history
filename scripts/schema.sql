-- ============================================================
-- DeepSeek History DB — схема
-- ============================================================

-- Диалоги
CREATE TABLE IF NOT EXISTS conversations (
    id              UUID PRIMARY KEY,
    title           TEXT,
    inserted_at     TIMESTAMPTZ,
    updated_at      TIMESTAMPTZ,
    source_file     TEXT,
    raw_mapping     JSONB,

    -- Поля для этапа 2 (классификация через LLM)
    topic           TEXT,
    summary         TEXT,
    status          TEXT,
    outcome         TEXT
);

-- Узлы дерева → сообщения
CREATE TABLE IF NOT EXISTS messages (
    id              BIGSERIAL PRIMARY KEY,
    node_id         TEXT NOT NULL,
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    parent_node_id  TEXT,
    role            TEXT NOT NULL,
    model           TEXT,
    inserted_at     TIMESTAMPTZ,
    position        INT,
    is_branch       BOOLEAN NOT NULL DEFAULT FALSE,

    UNIQUE (conversation_id, node_id)
);

-- Fragments внутри сообщения
CREATE TABLE IF NOT EXISTS fragments (
    id          BIGSERIAL PRIMARY KEY,
    message_id  BIGINT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    type        TEXT NOT NULL,
    content     TEXT,
    position    INT NOT NULL DEFAULT 0
);

-- ============================================================
-- Индексы
-- ============================================================

-- Быстрый поиск сообщений по диалогу и порядку
CREATE INDEX IF NOT EXISTS idx_messages_conv_pos
    ON messages (conversation_id, position);

-- Быстрый поиск fragments по сообщению
CREATE INDEX IF NOT EXISTS idx_fragments_msg_pos
    ON fragments (message_id, position);

-- Фильтрация по типу fragment (RESPONSE/REQUEST/...)
CREATE INDEX IF NOT EXISTS idx_fragments_type
    ON fragments (type);

-- Быстрый доступ к raw_mapping (JSONB)
CREATE INDEX IF NOT EXISTS idx_conversations_raw_gin
    ON conversations USING GIN (raw_mapping);

-- Поиск по датам
CREATE INDEX IF NOT EXISTS idx_conversations_inserted_at
    ON conversations (inserted_at);



-- ============================================================
-- Migration 002: sync support
-- ============================================================

-- Флаг «нужна классификация» — TRUE для новых/изменённых,
-- FALSE после успешной классификации.
ALTER TABLE conversations
    ADD COLUMN IF NOT EXISTS needs_classification BOOLEAN NOT NULL DEFAULT TRUE;

-- Когда диалог был удалён из источника (не удаляем из БД, но помечаем).
ALTER TABLE conversations
    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;

-- Индекс для быстрого поиска «что нужно классифицировать».
CREATE INDEX IF NOT EXISTS idx_conversations_needs_classification
    ON conversations (needs_classification)
    WHERE needs_classification = TRUE;





-- На будущее: полнотекстовый поиск по содержимому fragments
-- (раскомментируем на этапе RAG, когда будем делать tsvector)
-- CREATE INDEX idx_fragments_content_fts ON fragments USING GIN (to_tsvector('russian', content));
