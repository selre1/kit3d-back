from uuid import UUID

from psycopg2 import errors

from app.db.connection import get_db_connection


class DuplicateDemPathError(Exception):
    pass


def create_dem(dem_id: UUID, file_name: str, file_path: str, file_url: str) -> dict:
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO dem (dem_id, file_name, file_path, file_url)
                    VALUES (%s, %s, %s, %s)
                    RETURNING dem_id::text, file_name, file_path, file_url, created_at
                    """,
                    (str(dem_id), file_name, file_path, file_url),
                )
                row = cur.fetchone()
                return {
                    "dem_id": row[0],
                    "file_name": row[1],
                    "file_path": row[2],
                    "file_url": row[3],
                    "created_at": row[4],
                }
    except errors.UniqueViolation as exc:
        raise DuplicateDemPathError() from exc
    finally:
        conn.close()


def list_dems(limit: int = 100, offset: int = 0) -> list[dict]:
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        dem_id::text,
                        file_name,
                        file_path,
                        file_url,
                        created_at
                    FROM dem
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                )
                rows = cur.fetchall()

                return [
                    {
                        "dem_id": row[0],
                        "file_name": row[1],
                        "file_path": row[2],
                        "file_url": row[3],
                        "created_at": row[4],
                    }
                    for row in rows
                ]
    finally:
        conn.close()
