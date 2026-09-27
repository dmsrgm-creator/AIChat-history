"""
Утилиты для UI: форматирование, роли, экспорт в Markdown.
"""
from datetime import datetime, timezone


# ---------- Форматирование ----------

def fmt_dt(dt) -> str:
    """Форматирует дату в вид «YYYY-MM-DD HH:MM»."""
    if not dt:
        return "—"
    if isinstance(dt, str):
        return dt
    if isinstance(dt, datetime):
        # Если с таймзоной — приводим к локальному виду
        if dt.tzinfo is not None:
            dt = dt.astimezone()
        return dt.strftime("%Y-%m-%d %H:%M")
    return str(dt)


def fmt_chars(n: int) -> str:
    """Человекочитаемый объём: 1234 → 1.2k, 1234567 → 1.23M."""
    if not n:
        return "0"
    if n < 1000:
        return f"{n}"
    if n < 1_000_000:
        return f"{n/1000:.1f}k"
    return f"{n/1_000_000:.2f}M"


def fmt_msgs(n: int) -> str:
    """Склонение для количества сообщений."""
    n = int(n)
    if n % 10 == 1 and n % 100 != 11:
        return f"{n} сообщение"
    if 2 <= n % 10 <= 4 and not (12 <= n % 100 <= 14):
        return f"{n} сообщения"
    return f"{n} сообщений"


# ---------- Роли ----------

ROLE_EMOJI = {
    "user": "🧑",
    "assistant": "🤖",
    "tool": "🔧",
}

ROLE_TITLE = {
    "user": "Вы",
    "assistant": "DeepSeek",
    "tool": "Инструмент",
}


def role_emoji(role: str) -> str:
    return ROLE_EMOJI.get(role, "❓")


def role_title(role: str) -> str:
    return ROLE_TITLE.get(role, role)


# ---------- Экспорт в Markdown ----------

def conversation_to_markdown(conv: dict, messages: list[dict]) -> str:
    """
    Формирует Markdown-файл одного диалога.
    conv — dict из get_conversation.
    messages — list из get_messages.
    """
    lines = []

    # Шапка
    lines.append(f"# {conv.get('title') or 'Без названия'}\n")
    lines.append(f"- **ID:** `{conv['id']}`")
    lines.append(f"- **Создан:** {fmt_dt(conv.get('inserted_at'))}")
    lines.append(f"- **Обновлён:** {fmt_dt(conv.get('updated_at'))}")
    lines.append(f"- **Сообщений:** {len(messages)}")

    if conv.get("topic"):
        lines.append(f"- **Тема:** {conv['topic']}")
    if conv.get("status"):
        lines.append(f"- **Статус:** {conv['status']}")
    lines.append("")

    if conv.get("summary"):
        lines.append("## Резюме\n")
        lines.append(conv["summary"])
        lines.append("")

    if conv.get("outcome"):
        lines.append("## Результат\n")
        lines.append(conv["outcome"])
        lines.append("")

    lines.append("---\n")

    # Сообщения
    for m in messages:
        emoji = role_emoji(m["role"])
        title = role_title(m["role"])
        branch = " _(ветка)_" if m.get("is_branch") else ""
        ts = fmt_dt(m.get("inserted_at"))

        lines.append(f"## {emoji} {title} · {ts}{branch}\n")
        lines.append(f"*fragment: {m['frag_type']}*\n")
        lines.append(m["content"] or "_(пусто)_")
        lines.append("\n---\n")

    return "\n".join(lines)
