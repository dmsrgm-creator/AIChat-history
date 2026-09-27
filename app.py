"""
Streamlit UI для базы истории AI-чатов.

Запуск:
    streamlit run app.py
"""
import streamlit as st

from app.db import test_connection
from app.queries import (
    list_conversations,
    count_conversations,
    get_conversation,
    get_messages,
    search_in_content,
)
from app.utils import (
    fmt_dt,
    fmt_chars,
    fmt_msgs,
    role_emoji,
    role_title,
    conversation_to_markdown,
)


# ---------- Конфигурация страницы ----------
st.set_page_config(
    page_title="AI Chat History",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------- Состояние сессии ----------
if "selected_conv" not in st.session_state:
    st.session_state.selected_conv = None
if "page" not in st.session_state:
    st.session_state.page = 0
if "search_title" not in st.session_state:
    st.session_state.search_title = ""
if "search_content" not in st.session_state:
    st.session_state.search_content = ""


# ---------- Боковая панель ----------
with st.sidebar:
    st.title("🧠 AI Chat History")
    st.caption("История общения с AI")

    # Режимы
    mode = st.radio(
        "Режим",
        options=["📚 Диалоги", "🔎 Поиск по тексту", "ℹ️ О проекте"],
        index=0,
        label_visibility="collapsed",
    )

    st.divider()

    # Информация о БД
    try:
        info = test_connection()
        st.caption(f"БД: `{info['database']}`")
        st.caption(f"Сервер: {info['server_addr']}")
    except Exception as e:
        st.error(f"БД недоступна: {e}")

    st.divider()

    if st.button("🏠 К списку диалогов", use_container_width=True):
        st.session_state.selected_conv = None
        st.session_state.page = 0
        st.rerun()

    st.caption("v0.1.0 · MIT")


# ======================================================================
# ЭКРАН 1: Конкретный диалог (приоритетный — если выбран)
# ======================================================================
if st.session_state.selected_conv:
    conv = get_conversation(st.session_state.selected_conv)
    if not conv:
        st.error("Диалог не найден.")
        st.session_state.selected_conv = None
        st.rerun()

    # Кнопка назад
    if st.button("← Назад к списку"):
        st.session_state.selected_conv = None
        st.rerun()

    st.title(conv["title"] or "_(без заголовка)_")

    # Метрики
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Создан", fmt_dt(conv.get("inserted_at")))
    col2.metric("Обновлён", fmt_dt(conv.get("updated_at")))
    col3.metric("Тема", conv.get("topic") or "—")
    col4.metric("Статус", conv.get("status") or "—")

    if conv.get("summary"):
        st.info(f"**Резюме:** {conv['summary']}")

    if conv.get("outcome"):
        st.success(f"**Результат:** {conv['outcome']}")

    st.divider()

    # Сообщения
    messages = get_messages(conv["id"])

    col_a, col_b = st.columns([1, 5])
    with col_a:
        md = conversation_to_markdown(conv, messages)
        st.download_button(
            "📥 Скачать Markdown",
            data=md.encode("utf-8"),
            file_name=f"dialog_{str(conv['id'])[:8]}.md",  # file_name=f"dialog_{conv['id'][:8]}.md",
            mime="text/markdown",
            use_container_width=True,
        )
    with col_b:
        st.caption(f"{fmt_msgs(len(messages))} · {fmt_chars(sum(len(m['content'] or '') for m in messages))}")

    if not messages:
        st.warning("Сообщений нет.")
    else:
        # Переключатель «показывать ветки»
        show_branches = st.checkbox("Показывать ответвления (regenerations)", value=False)

        visible = [m for m in messages if show_branches or not m.get("is_branch")]

        for i, m in enumerate(visible):
            emoji = role_emoji(m["role"])
            title = role_title(m["role"])
            branch = " · _ветка_" if m.get("is_branch") else ""
            header = f"{emoji} **{title}** · #{m['msg_pos']} · {fmt_dt(m.get('inserted_at'))}{branch}"

            with st.expander(header, expanded=(i < 2)):
                st.caption(f"`{m['frag_type']}` · {len(m['content'] or '')} симв.")
                st.markdown(m["content"] or "_(пусто)_")

    st.stop()


# ======================================================================
# ЭКРАН 2: Список диалогов
# ======================================================================
if mode == "📚 Диалоги":
    st.title("📚 Диалоги")

    col1, col2 = st.columns([4, 1])
    with col1:
        search = st.text_input(
            "Фильтр по заголовку",
            value=st.session_state.search_title,
            placeholder="например: Квант, Kia, Home Assistant",
            label_visibility="collapsed",
        )
        st.session_state.search_title = search
    with col2:
        per_page = st.selectbox("На странице", [25, 50, 100, 200], index=1, label_visibility="collapsed")

    total = count_conversations(search)
    total_pages = max(1, (total + per_page - 1) // per_page)

    # Пагинация
    col_l, col_c, col_r = st.columns([1, 3, 1])
    with col_l:
        if st.button("← Назад", use_container_width=True) and st.session_state.page > 0:
            st.session_state.page -= 1
            st.rerun()
    with col_c:
        st.markdown(
            f"<div style='text-align:center; padding-top:6px'>"
            f"Страница <b>{st.session_state.page + 1}</b> из <b>{total_pages}</b> "
            f"· всего <b>{total}</b> диалогов"
            f"</div>",
            unsafe_allow_html=True,
        )
    with col_r:
        if st.button("Вперёд →", use_container_width=True) and st.session_state.page < total_pages - 1:
            st.session_state.page += 1
            st.rerun()

    st.divider()

    convs = list_conversations(search, limit=per_page, offset=st.session_state.page * per_page)

    if not convs:
        st.warning("Ничего не найдено.")
    else:
        for c in convs:
            with st.container(border=True):
                col1, col2, col3, col4, col5 = st.columns([6, 1, 1, 1.5, 1])
                with col1:
                    st.markdown(f"**{c['title'] or '_(без заголовка)_'}**")
                with col2:
                    st.caption(f"💬 {c['msg_count']}")
                with col3:
                    st.caption(fmt_chars(c["chars"]))
                with col4:
                    st.caption(fmt_dt(c["updated_at"]))
                with col5:
                    if st.button("Открыть", key=f"open_{c['id']}", use_container_width=True):
                        st.session_state.selected_conv = c["id"]
                        st.rerun()


# ======================================================================
# ЭКРАН 3: Поиск по тексту
# ======================================================================
elif mode == "🔎 Поиск по тексту":
    st.title("🔎 Поиск по содержимому")
    st.caption("Найдёт все диалоги, где встречается слово или фраза.")

    query = st.text_input(
        "Что искать",
        value=st.session_state.search_content,
        placeholder="например: квант, глюон, Home Assistant",
        label_visibility="collapsed",
    )
    st.session_state.search_content = query

    if query and len(query.strip()) >= 2:
        with st.spinner("Ищу..."):
            results = search_in_content(query, limit=100)

        if not results:
            st.warning(f"Ничего не найдено по запросу «{query}»")
        else:
            st.success(f"Найдено диалогов: **{len(results)}**")
            for r in results:
                with st.container(border=True):
                    col1, col2, col3, col4 = st.columns([6, 1, 1.5, 1])
                    with col1:
                        st.markdown(f"**{r['title'] or '_(без заголовка)_'}**")
                    with col2:
                        st.caption(f"🎯 {r['hits']}")
                    with col3:
                        st.caption(fmt_dt(r["inserted_at"]))
                    with col4:
                        if st.button("Открыть", key=f"s_{r['id']}", use_container_width=True):
                            st.session_state.selected_conv = r["id"]
                            st.rerun()
    elif query:
        st.info("Введите минимум 2 символа.")


# ======================================================================
# ЭКРАН 4: О проекте
# ======================================================================
elif mode == "ℹ️ О проекте":
    st.title("ℹ️ О проекте")
    st.markdown("""
**AI Chat History** — инструмент для структурирования и просмотра истории общения с AI-чатами (DeepSeek, и в будущем другие).

### Что делает
- Парсит JSON-экспорт диалогов DeepSeek
- Складывает в PostgreSQL: диалоги → сообщения → fragments (запросы, ответы, thinking, поиск)
- Даёт веб-интерфейс на Streamlit: список, поиск, просмотр, экспорт в Markdown

### Стек
- PostgreSQL 15
- Python 3.12 + psycopg 3
- Streamlit

### Планы
- LLM-классификация диалогов (тема, резюме, статус, milestones)
- Полнотекстовый поиск с русской морфологией
- RAG: задавать вопросы по своей истории

### Ссылки
- [GitHub](https://github.com/dmsrgm-creator/AIChat-history)
- Лицензия: MIT
""")
