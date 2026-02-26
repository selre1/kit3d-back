import os
from pathlib import Path

import psycopg2

def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        dbname=os.getenv("DB_NAME", "tile_worker"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "admin"),
    )


def ensure_migrations_table(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
              version TEXT PRIMARY KEY,
              applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )


def get_applied(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT version FROM schema_migrations")
        return {row[0] for row in cur.fetchall()}


def apply_migration(conn, version, sql_text):
    with conn.cursor() as cur:
        cur.execute(sql_text)
        cur.execute(
            "INSERT INTO schema_migrations (version) VALUES (%s)",
            (version,),
        )


def main():
    migrations_dir = Path(os.getenv("MIGRATIONS_DIR", "migrations"))
    if not migrations_dir.exists():
        raise SystemExit(f"Migrations directory not found: {migrations_dir}")

    files = sorted(p for p in migrations_dir.glob("*.sql") if p.is_file())
    if not files:
        print("No migrations found.")
        return

    conn = get_connection()
    try:
        conn.autocommit = False
        ensure_migrations_table(conn)
        applied = get_applied(conn)

        for path in files:
            version = path.name
            if version in applied:
                continue
            sql_text = path.read_text(encoding="utf-8")
            print(f"Applying {version}...")
            apply_migration(conn, version, sql_text)
            conn.commit()
            print(f"Applied {version}.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
