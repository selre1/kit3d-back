from uuid import UUID

from psycopg2 import errors

from app.db.connection import get_db_connection


class ProjectAlreadyExistsError(Exception):
    pass


def project_exists(project_id: UUID) -> bool:
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM project WHERE project_id = %s",
                    (str(project_id),),
                )
                return cur.fetchone() is not None
    finally:
        conn.close()


def get_project_format(project_id: UUID) -> str | None:
    """프로젝트의 모델 타입. 프로젝트가 없으면 None."""
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT format FROM project WHERE project_id = %s",
                    (str(project_id),),
                )
                row = cur.fetchone()
                return row[0] if row else None
    finally:
        conn.close()


def insert_project(
    project_id: UUID,
    name: str,
    file_format: str,
    description: str | None = None,
) -> dict:
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO project (project_id, name, description, format, created_at)
                    VALUES (%s, %s, %s, %s, NOW())
                    RETURNING project_id, name, description, format, created_at
                    """,
                    (str(project_id), name, description, file_format),
                )
                row = cur.fetchone()
                return {
                    "project_id": row[0],
                    "name": row[1],
                    "description": row[2],
                    "format": row[3],
                    "created_at": row[4],
                    "models_count": 0,
                }
    except errors.UniqueViolation as exc:
        raise ProjectAlreadyExistsError() from exc
    finally:
        conn.close()


def fetch_projects(
    limit: int = 50,
    offset: int = 0,
    file_format: str | None = None,
) -> list[dict]:
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        p.project_id,
                        p.name,
                        p.description,
                        p.format,
                        p.created_at,
                        COALESCE(u.models_count, 0) AS models_count
                    FROM project p
                    LEFT JOIN (
                        SELECT project_id, COUNT(*) AS models_count
                        FROM upload_file
                        GROUP BY project_id
                    ) u ON u.project_id = p.project_id
                    WHERE (%s::text IS NULL OR p.format = %s)
                    ORDER BY p.created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (file_format, file_format, limit, offset),
                )
                return [
                    {
                        "project_id": row[0],
                        "name": row[1],
                        "description": row[2],
                        "format": row[3],
                        "created_at": row[4],
                        "models_count": row[5],
                    }
                    for row in cur.fetchall()
                ]
    finally:
        conn.close()
