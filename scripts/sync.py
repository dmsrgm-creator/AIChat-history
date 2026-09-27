"""
Синхронизация БД с JSON-экспортом DeepSeek.

Что делает:
  - Новые диалоги         → INSERT + needs_classification=TRUE
  - Изменённые диалоги    → UPDATE + needs_classification=TRUE
                            (классификация сбрасывается, т.к. содержимое новое)
  - Без изменений         → SKIP (классификация сохраняется)
  - Диалоги, которых нет в новом файле → не трогаем (архив)

Запуск:
    python scripts/sync.py data/21092026.json
    python scripts/sync.py data/21092026.json --dry-run
"""
import argparse
import json
import os
import sys
import time

import psycopg
from datetime import datetime
from psycopg.types.json import Jsonb
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parse import parse_conversation  # noqa: E402



def get_conn_str() -> str:
    load_dotenv()
    return (
        f"host={os.getenv('PGHOST')} "
        f"port={os.getenv('PGPORT')} "
        f"user={os.getenv('PGUSER')} "
        f"password={os.getenv('PGPASSWORD')} "
        f"dbname={os.getenv('PGDATABASE')}"
    )

def parse_dt(s) -> datetime:
    """Приводит строку ISO или datetime к datetime."""
    if isinstance(s, datetime):
        return s
    return datetime.fromisoformat(s)

def load_existing(cur) -> dict:
    """Возвращает {id: updated_at} для всех диалогов в БД."""
    cur.execute("SELECT id, updated_at FROM conversations")
    return {str(row[0]): row[1] for row in cur.fetchall()}


def insert_conversation(cur, conv: dict):
    """INSERT нового диалога + messages + fragments."""
    cur.execute(
        """
        INSERT INTO conversations
            (id, title, inserted_at, updated_at, source_file, raw_mapping,
             needs_classification)
        VALUES (%s, %s, %s, %s, %s, %s, TRUE)
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

        for fr in msg["fragments"]:
            cur.execute(
                """
                INSERT INTO fragments (message_id, type, content, position)
                VALUES (%s, %s, %s, %s)
                """,
                (message_id, fr["type"], fr["content"], fr["position"]),
            )


def delete_conversation(cur, conv_id):
    """
    Удаляем диалог (каскадом уйдут messages и fragments).
    Используется перед повторной вставкой при UPDATE.
    """
    cur.execute("DELETE FROM conversations WHERE id = %s", (conv_id,))


def update_conversation(cur, conv: dict):
    """
    Обновляем диалог: удаляем старый + вставляем новый.
    Классификация сбрасывается (needs_classification=TRUE).
    """
    delete_conversation(cur, conv["id"])
    insert_conversation(cur, conv)


def main():
    parser = argparse.ArgumentParser(description="Sync DB with DeepSeek export")
    parser.add_argument("source", help="Path to JSON export file")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only show what would change, don't touch DB",
    )
    args = parser.parse_args()

    if not os.path.exists(args.source):
        print(f"Файл не найден: {args.source}", file=sys.stderr)
        sys.exit(1)

    print(f"Читаю {args.source}...")
    t0 = time.time()
    with open(args.source, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"  загружено {len(data)} диалогов за {time.time()-t0:.1f}с")

    print("Парсю...")
    t0 = time.time()
    parsed = [parse_conversation(c, args.source) for c in data]
    print(f"  распарсено за {time.time()-t0:.1f}с")

    print("Подключаюсь к БД...")
    conn_str = get_conn_str()

    with psycopg.connect(conn_str) as conn:
        with conn.cursor() as cur:
            existing = load_existing(cur)
            print(f"  в БД уже {len(existing)} диалогов")

            to_insert = []
            to_update = []
            to_skip = 0

            for conv in parsed:
                cid = conv["id"]
                if cid not in existing:
                    to_insert.append(conv)
                elif parse_dt(conv["updated_at"]) > parse_dt(existing[cid]): #elif conv["updated_at"] > existing[cid]:
                    to_update.append(conv)
                else:
                    to_skip += 1

            in_db_only = len(set(existing.keys()) - {c["id"] for c in parsed})

            print()
            print(f"  Новых:                    {len(to_insert)}")
            print(f"  Изменённых:               {len(to_update)}")
            print(f"  Без изменений:            {to_skip}")
            print(f"  Только в БД (нет в файле): {in_db_only}")

            if args.dry_run:
                print()
                print("--dry-run: ничего не меняем.")
                return

            if not to_insert and not to_update:
                print()
                print("Нечего синхронизировать. Всё актуально.")
                return

            print()
            print("Применяю изменения...")
            t0 = time.time()

            for i, conv in enumerate(to_insert, 1):
                insert_conversation(cur, conv)
                if i % 50 == 0:
                    print(f"  INSERT: {i}/{len(to_insert)}")

            for i, conv in enumerate(to_update, 1):
                update_conversation(cur, conv)
                if i % 50 == 0:
                    print(f"  UPDATE: {i}/{len(to_update)}")

            print(f"  готово за {time.time()-t0:.1f}с")

    print()
    print("Проверяю результат...")
    with psycopg.connect(conn_str) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM conversations")
            print(f"  conversations:           {cur.fetchone()[0]}")
            cur.execute("SELECT count(*) FROM messages")
            print(f"  messages:                {cur.fetchone()[0]}")
            cur.execute("SELECT count(*) FROM fragments")
            print(f"  fragments:               {cur.fetchone()[0]}")
            cur.execute(
                "SELECT count(*) FROM conversations WHERE needs_classification = TRUE"
            )
            print(f"  ждут классификации:      {cur.fetchone()[0]}")




if __name__ == "__main__":
    main()
