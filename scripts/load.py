"""
Загрузка распарсенного JSON в Postgres.
Идемпотентно: если диалог с таким id уже есть — пропускаем.
"""
import json
import os
import sys
import time

import psycopg
from psycopg.types.json import Jsonb
from dotenv import load_dotenv

from parse import parse_conversation


def get_conn_str() -> str:
    load_dotenv()
    return (
        f"host={os.getenv('PGHOST')} "
        f"port={os.getenv('PGPORT')} "
        f"user={os.getenv('PGUSER')} "
        f"password={os.getenv('PGPASSWORD')} "
        f"dbname={os.getenv('PGDATABASE')}"
    )


def main():
    source_file = "21092026.json"
    if not os.path.exists(source_file):
        print(f"Файл {source_file} не найден", file=sys.stderr)
        sys.exit(1)

    print(f"Читаю {source_file}...")
    t0 = time.time()
    with open(source_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"  загружено {len(data)} диалогов за {time.time()-t0:.1f}с")

    print("Парсю диалоги...")
    t0 = time.time()
    parsed_convos = [parse_conversation(c, source_file) for c in data]
    print(f"  распарсено за {time.time()-t0:.1f}с")

    print("Подключаюсь к БД...")
    conn_str = get_conn_str()

    with psycopg.connect(conn_str) as conn:
        with conn.cursor() as cur:
            # Проверим, что уже есть (идемпотентность)
            cur.execute("SELECT count(*) FROM conversations")
            existing = cur.fetchone()[0]
            if existing:
                print(f"  в БД уже {existing} диалогов.")
                ans = input("  Продолжить (дубликаты будут пропущены)? [y/N]: ").strip().lower()
                if ans != "y":
                    print("Отмена.")
                    return

            # Узнаём, какие id уже есть — чтобы не дублировать
            cur.execute("SELECT id FROM conversations")
            existing_ids = {row[0] for row in cur.fetchall()}

            # Отсеиваем уже загруженные диалоги
            to_load = [c for c in parsed_convos if c["id"] not in existing_ids]
            if not to_load:
                print("  всё уже загружено, нечего делать.")
                return
            print(f"  к загрузке: {len(to_load)} диалогов")

            # Счётчики
            n_conv = 0
            n_msg = 0
            n_frag = 0

            t0 = time.time()
            for i, conv in enumerate(to_load, 1):
                # 1) Диалог
                cur.execute(
                    """
                    INSERT INTO conversations
                        (id, title, inserted_at, updated_at, source_file, raw_mapping)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        conv["id"],
                        conv["title"],
                        conv["inserted_at"],
                        conv["updated_at"],
                        conv["source_file"],
                        Jsonb(conv["raw_mapping"]),
                    ),
                )
                n_conv += 1

                # 2) Сообщения
                for msg in conv["messages"]:
                    cur.execute(
                        """
                        INSERT INTO messages
                            (node_id, conversation_id, parent_node_id, role,
                             model, inserted_at, position, is_branch)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            msg["node_id"],
                            conv["id"],
                            msg["parent_node_id"],
                            msg["role"],
                            msg["model"],
                            msg["inserted_at"],
                            msg["position"],
                            msg["is_branch"],
                        ),
                    )
                    message_id = cur.fetchone()[0]
                    n_msg += 1

                    # 3) Fragments
                    for fr in msg["fragments"]:
                        cur.execute(
                            """
                            INSERT INTO fragments (message_id, type, content, position)
                            VALUES (%s, %s, %s, %s)
                            """,
                            (message_id, fr["type"], fr["content"], fr["position"]),
                        )
                        n_frag += 1

                if i % 50 == 0:
                    print(f"  обработано {i}/{len(to_load)} диалогов "
                          f"(msg: {n_msg}, frag: {n_frag}, {time.time()-t0:.1f}с)")

            print(f"  готово: диалогов={n_conv}, сообщений={n_msg}, fragments={n_frag}")
            print(f"  время: {time.time()-t0:.1f}с")

    # Финальная проверка (новая транзакция)
    print("Проверяю результат...")
    with psycopg.connect(conn_str) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM conversations")
            print("  conversations:", cur.fetchone()[0])
            cur.execute("SELECT count(*) FROM messages")
            print("  messages:     ", cur.fetchone()[0])
            cur.execute("SELECT count(*) FROM fragments")
            print("  fragments:    ", cur.fetchone()[0])


if __name__ == "__main__":
    main()
