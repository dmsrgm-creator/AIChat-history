"""
SQL-запросы для UI.
Все параметры — через placeholders (%s или %(name)s), никакой конкатенации.
"""
from app.db import get_conn


def count_conversations(search: str = "") -> int:
    """Сколько диалогов (с учётом фильтра по заголовку)."""
    sql = """
        SELECT count(*)
        FROM conversations
        WHERE (%(search)s = '' OR title ILIKE '%%' || %(search)s || '%%')
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"search": search})
            return cur.fetchone()[0]


def list_conversations(search: str = "", limit: int = 50, offset: int = 0) -> list[dict]:
    """
    Список диалогов с метаданными:
    id, title, даты, число сообщений, объём в символах.
    """
    sql = """
        SELECT
            c.id,
            c.title,
            c.inserted_at,
            c.updated_at,
            c.topic,
            c.status,
            (SELECT count(*) FROM messages m WHERE m.conversation_id = c.id) AS msg_count,
            (SELECT coalesce(sum(length(f.content)), 0)
               FROM messages m
               JOIN fragments f ON f.message_id = m.id
              WHERE m.conversation_id = c.id) AS chars
        FROM conversations c
        WHERE (%(search)s = '' OR c.title ILIKE '%%' || %(search)s || '%%')
        ORDER BY c.updated_at DESC NULLS LAST
        LIMIT %(limit)s OFFSET %(offset)s
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"search": search, "limit": limit, "offset": offset})
            cols = [d.name for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


def get_conversation(conv_id: str) -> dict | None:
    """Метаданные одного диалога."""
    sql = """
        SELECT id, title, inserted_at, updated_at,
               topic, summary, status, outcome
        FROM conversations
        WHERE id = %s
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (conv_id,))
            row = cur.fetchone()
            if not row:
                return None
            cols = [d.name for d in cur.description]
            return dict(zip(cols, row))


def get_messages(conv_id: str) -> list[dict]:
    """
    Все fragments диалога в порядке position.
    Один fragment = одна строка.
    """
    sql = """
        SELECT
            m.position AS msg_pos,
            m.role,
            m.inserted_at,
            m.is_branch,
            f.type AS frag_type,
            f.content
        FROM messages m
        JOIN fragments f ON f.message_id = m.id
        WHERE m.conversation_id = %s
        ORDER BY m.position, f.position
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (conv_id,))
            cols = [d.name for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


def search_in_content(query: str, limit: int = 50) -> list[dict]:
    """
    Поиск подстроки (ILIKE) по содержимому fragments.
    Возвращает диалоги, где встречается, и число совпадений.
    """
    if not query or len(query.strip()) < 2:
        return []

    sql = """
        SELECT
            c.id,
            c.title,
            c.inserted_at,
            count(*) AS hits
        FROM conversations c
        JOIN messages m ON m.conversation_id = c.id
        JOIN fragments f ON f.message_id = m.id
        WHERE f.content ILIKE '%%' || %(q)s || '%%'
        GROUP BY c.id, c.title, c.inserted_at
        ORDER BY hits DESC, c.inserted_at DESC
        LIMIT %(limit)s
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"q": query, "limit": limit})
            cols = [d.name for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
