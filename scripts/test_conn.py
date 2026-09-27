import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

conn_str = (
    f"host={os.getenv('PGHOST')} "
    f"port={os.getenv('PGPORT')} "
    f"user={os.getenv('PGUSER')} "
    f"password={os.getenv('PGPASSWORD')} "
    f"dbname={os.getenv('PGDATABASE')}"
)

with psycopg.connect(conn_str) as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT current_user, current_database(), inet_server_addr(), version()
        """)
        row = cur.fetchone()
        print("user:      ", row[0])
        print("database:  ", row[1])
        print("server ip: ", row[2])
        print("version:   ", row[3][:60], "...")

        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        tables = [r[0] for r in cur.fetchall()]
        print("tables:    ", tables)
