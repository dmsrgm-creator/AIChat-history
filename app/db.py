"""
Подключение к PostgreSQL.
Параметры берутся из .env (см. .env.example).
"""
import os
import psycopg
from dotenv import load_dotenv

load_dotenv()


def get_conn_str() -> str:
    """Собирает строку подключения из переменных окружения."""
    return (
        f"host={os.getenv('PGHOST')} "
        f"port={os.getenv('PGPORT')} "
        f"user={os.getenv('PGUSER')} "
        f"password={os.getenv('PGPASSWORD')} "
        f"dbname={os.getenv('PGDATABASE')}"
    )


def get_conn():
    """Возвращает новое соединение с БД.
    Каждый вызов — новое соединение. Streamlit перезапускает скрипт
    на каждое действие, поэтому долгоживущее соединение тут не нужно.
    """
    return psycopg.connect(get_conn_str())


def test_connection():
    """Быстрая проверка соединения. Возвращает dict с метаданными."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    current_user,
                    current_database(),
                    inet_server_addr(),
                    version()
            """)
            row = cur.fetchone()
            return {
                "user": row[0],
                "database": row[1],
                "server_addr": str(row[2]) if row[2] else "local",
                "version": row[3].split(",")[0],
            }
