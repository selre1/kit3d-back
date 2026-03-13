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


def insert_project(project_id: UUID, name: str, description: str | None = None) -> dict:
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO project (project_id, name, description, created_at)
                    VALUES (%s, %s, %s, NOW())
                    RETURNING project_id, name, description, created_at
                    """,
                    (str(project_id), name, description),
                )
                row = cur.fetchone()
                if not row:
                    return {
                        "project_id": project_id,
                        "name": name,
                        "description": description,
                        "created_at": None,
                        "upload_completed_count": 0,
                    }
                return {
                    "project_id": row[0],
                    "name": row[1],
                    "description": row[2],
                    "created_at": row[3],
                    "upload_completed_count": 0,
                }
    except errors.UniqueViolation as exc:
        raise ProjectAlreadyExistsError() from exc
    finally:
        conn.close()


def fetch_projects(limit: int = 50, offset: int = 0) -> list[dict]:
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
                        p.created_at,
                        COALESCE(u.completed_count, 0) AS models_count
                    FROM project p
                    LEFT JOIN (
                        SELECT project_id, COUNT(DISTINCT job_id) AS completed_count
                        FROM ifc_object
                        GROUP BY project_id
                    ) u ON u.project_id = p.project_id
                    ORDER BY p.created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                )
                return [
                    {
                        "project_id": row[0],
                        "name": row[1],
                        "description": row[2],
                        "created_at": row[3],
                        "models_count": row[4],
                    }
                    for row in cur.fetchall()
                ]
    finally:
        conn.close()
